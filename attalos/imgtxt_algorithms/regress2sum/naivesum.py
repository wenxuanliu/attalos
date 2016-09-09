import numpy as np
import tensorflow as tf
from itertools import izip

from attalos.imgtxt_algorithms.regress2sum.attalos_model import AttalosModel
from attalos.dataset.transformers.onehot import OneHot
from attalos.dataset.transformers.newnaivew2v import NaiveW2V

import attalos.util.log.log as l

# Setup global objects
logger = l.getLogger(__name__)

class NaiveSumModel(AttalosModel):
    """
    This model performs linear regression via NN using the naive sum of word vectors as targets.
    """
    def _construct_model_info(self, input_size, output_size, learning_rate):
        logger.info("Input size: %s" % input_size)
        logger.info("Output size: %s" % output_size)
        
        model_info = {}
        model_info["input"] = tf.placeholder(shape=(None, input_size), dtype=tf.float32)
        model_info["y_truth"] = tf.placeholder(shape=(None, output_size), dtype=tf.float32)
        
        #hidden_layer = tf.contrib.layers.relu(model_info["input"], 1124)
        hidden_layer1 = tf.contrib.layers.relu(model_info["input"], 1686)
        hidden_layer2 = tf.contrib.layers.relu(hidden_layer1, 1124)
        hidden_layer3 = tf.contrib.layers.relu(hidden_layer2, 562)
        
        model_info["predictions"] = tf.contrib.layers.fully_connected(hidden_layer3,
                                                                      output_size,
                                                                      activation_fn=None)
        model_info["loss"] = tf.reduce_sum(tf.square(model_info["predictions"] - model_info["y_truth"]))
        model_info["optimizer"] = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(model_info["loss"])
        return model_info
    
    def __init__(self, wv_model, train_dataset, test_dataset, **kwargs):
        self.wv_model = wv_model
        self.cross_eval = kwargs.get("cross_eval", False)
        self.one_hot = OneHot([train_dataset] if self.cross_eval else [train_dataset, test_dataset], 
                              valid_vocab=wv_model.vocab)
        self.wv_transformer = NaiveW2V.create_from_vocab(wv_model, self.one_hot, vocab=self.one_hot.get_key_ordering())
        self.learning_rate = kwargs.get("learning_rate", 0.0001)
        self.model_info = self._construct_model_info(
                input_size = train_dataset.img_feat_size,
                output_size = self.wv_model.get_word_vector_shape()[0], 
                learning_rate = self.learning_rate
        )
        super(NaiveSumModel, self).__init__()

    # is a generator
    def to_batches(self, dataset, batch_size):
        # TODO batch_size = -1 should yield the entire dataset
        num_batches = int(dataset.num_images / batch_size)
        for batch in xrange(num_batches):
            img_feats_list, text_feats_list = dataset.get_next_batch(batch_size)

            new_img_feats = np.array(img_feats_list)
            # normalize img_feats
            #new_img_feats = (new_img_feats.T / np.linalg.norm(new_img_feats, axis=1)).T

            new_text_feats = [self.one_hot.get_multiple(text_feats) for text_feats in text_feats_list]
            new_text_feats = np.array(new_text_feats)
            new_text_feats = self.wv_transformer.transform(new_text_feats)
            # normalize text feats
            # new_text_feats = (new_text_feats.T / np.linalg.norm(new_text_feats, axis=1)).T

            yield new_img_feats, new_text_feats
    
    def to_ndarrs(self, dataset):
        x = []
        y = []
        for idx in dataset:
            image_feats, text_feats = dataset.get_index(idx)
            text_feats = self.one_hot.get_multiple(text_feats)
            x.append(image_feats)
            y.append(text_feats)
        return np.asarray(x), np.asarray(y)
        
    def fit(self, sess, x, y, **kwargs):
        _, loss = sess.run([self.model_info["optimizer"], self.model_info["loss"]],
                           feed_dict={
                               self.model_info["input"]: x,
                               self.model_info["y_truth"]: y
                           })
        return loss
        
    def predict(self, sess, x, y=None):
        fetches = [self.model_info["predictions"]]
        feed_dict = {self.model_info["input"]: x}
        #if y is not None:
        #    logger.info("Ignoring y. Cannot evaluate test loss with naivesum model.")
        #    fetches.append(self.model_info["loss"])
        #    feed_dict[self.model_info["y_truth"]] = y
        predictions = sess.run(fetches, feed_dict=feed_dict)
        #if y is not None:
        #    predictions = fetches[0]
        #    loss = fetches[1]
        #else: 
        #    predictions = fetches
        predictions = predictions[0] # predictions is a list
        predictions = NaiveW2V.to_multihot(self.wv_model, self.one_hot, predictions, k=5)    
        return predictions


