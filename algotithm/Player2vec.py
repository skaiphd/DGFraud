import tensorflow as tf
from base_models.model import GCN
from base_models.layers import SimpleAttLayer


class Player2Vec(object):
    '''
    Player2Vec ('Key Player Identification in Underground Forums
    over Attributed Heterogeneous Information Network Embedding Framework')

    Parameters:
        meta: meta-path number
        nodes: total nodes number
        gcn_output1: the first gcn layer units number
        gcn_output2: the second gcn layer units number
        embedding: node feature dim
        encoding: nodes representation dim
    '''

    def __init__(self,
                 session,
                 meta,
                 nodes,
                 class_size,
                 gcn_output1,
                 gcn_output2,
                 embedding,
                 encoding):
        self.meta = meta
        self.nodes = nodes
        self.class_size = class_size
        self.gcn_output1 = gcn_output1
        self.gcn_output2 = gcn_output2
        self.embedding = embedding
        self.encoding = encoding

        self.build_placeholders()

        loss, probabilities, features = self.forward_propagation()
        self.loss, self.probabilities, self.features = loss, probabilities, features
        self.l2 = tf.contrib.layers.apply_regularization(tf.contrib.layers.l2_regularizer(0.01),
                                                         tf.trainable_variables())

        self.pred = tf.one_hot(tf.argmax(self.probabilities, 1), class_size)
        print(self.pred.shape)
        self.correct_prediction = tf.equal(tf.argmax(self.probabilities, 1), tf.argmax(self.t, 1))
        self.accuracy = tf.reduce_mean(tf.cast(self.correct_prediction, "float"))
        print('Forward propagation finished.')

        self.sess = session
        self.optimizer = tf.train.AdamOptimizer(self.lr)
        gradients = self.optimizer.compute_gradients(self.loss + self.l2)
        capped_gradients = [(tf.clip_by_value(grad, -5., 5.), var) for grad, var in gradients if grad is not None]
        self.train_op = self.optimizer.apply_gradients(capped_gradients)
        self.init = tf.global_variables_initializer()
        print('Backward propagation finished.')

    def build_placeholders(self):
        self.a = tf.placeholder(tf.float32, [self.meta, self.nodes, self.nodes], 'adj')
        self.x = tf.placeholder(tf.float32, [self.nodes, self.embedding], 'nxf')
        self.batch_index = tf.placeholder(tf.int32, [None], 'index')
        self.t = tf.placeholder(tf.float32, [None, self.class_size], 'labels')
        self.lr = tf.placeholder(tf.float32, [], 'learning_rate')
        self.mom = tf.placeholder(tf.float32, [], 'momentum')

    def forward_propagation(self):
        with tf.variable_scope('gcn'):
            x = self.x
            A = tf.reshape(self.a, [self.meta, self.nodes, self.nodes])
            gcn_emb = []
            for i in range(self.meta):
                gcn_out = tf.reshape(GCN(x, A[i], self.gcn_output1, self.gcn_output2, self.embedding,
                                         self.encoding).embedding(), [1, self.nodes * self.encoding])
                gcn_emb.append(gcn_out)
            gcn_emb = tf.concat(gcn_emb, 0)
            assert gcn_emb.shape == [self.meta, self.nodes * self.encoding]
            print('GCN embedding over!')

        with tf.variable_scope('attention'):
            gat_out = SimpleAttLayer.attention(inputs=gcn_emb, attention_size=1)
            gat_out = tf.reshape(gat_out, [self.nodes, self.encoding])
            print('Embedding with attention over!')

        with tf.variable_scope('classification'):
            batch_data = tf.matmul(tf.one_hot(self.batch_index, self.nodes), gat_out)
            W = tf.get_variable(name='weights', shape=[self.encoding, self.class_size],
                                initializer=tf.contrib.layers.xavier_initializer())
            b = tf.get_variable(name='bias', shape=[1, self.class_size], initializer=tf.zeros_initializer())
            tf.transpose(batch_data, perm=[0, 1])
            logits = tf.matmul(batch_data, W) + b
            loss = tf.losses.sigmoid_cross_entropy(multi_class_labels=self.t, logits=logits)

        return loss, tf.nn.sigmoid(logits), gcn_out[0]

    def train(self, x, a, t, b, learning_rate=1e-2, momentum=0.9):
        feed_dict = {
            self.x: x,
            self.a: a,
            self.t: t,
            self.batch_index: b,
            self.lr: learning_rate,
            self.mom: momentum
        }
        outs = self.sess.run(
            [self.train_op, self.loss, self.accuracy, self.pred, self.probabilities],
            feed_dict=feed_dict)
        loss = outs[1]
        acc = outs[2]
        pred = outs[3]
        prob = outs[4]
        return loss, acc, pred, prob

    def save(self, sess=None):
        if not sess:
            raise AttributeError("TensorFlow session not provided.")
        saver = tf.train.Saver()
        save_path = saver.save(sess, "tmp/%s.ckpt" % 'temp')
        print("Model saved in file: %s" % save_path)

    def load(self, sess=None):
        if not sess:
            raise AttributeError("TensorFlow session not provided.")
        saver = tf.train.Saver()
        save_path = "tmp/%s.ckpt" % 'temp'
        saver.restore(sess, save_path)
        print("Model restored from file: %s" % save_path)

    def test(self, x, a, t, b):
        feed_dict = {
            self.x: x,
            self.a: a,
            self.t: t,
            self.batch_index: b
        }
        acc, pred, features, probabilities, tags = self.sess.run(
            [self.accuracy, self.pred, self.features, self.probabilities, self.correct_prediction],
            feed_dict=feed_dict)
        return acc, pred, features, probabilities, tags
