# coding = utf-8

import data_helper
import tensorflow as tf
import datetime
import numpy as np
from sklearn.model_selection import train_test_split
from TextCNN_model import *

# Parameters /sohu_algorithm_competition
# =======================================================
# Data and model loading parameters
tf.flags.DEFINE_string('train_data_file', './data_bunch/cnn_non_stop_words_train_bunch.dat', 'Data for training')
tf.flags.DEFINE_string('train_label_file', './data_bunch/cnn_train_label_bunch.dat', 'Some infomation for train data,such as label, picture list and so on')
tf.flags.DEFINE_string('unlabel_data_file', './data_bunch/cnn_non_stop_words_unlabel_news_bunch.dat', 'use for embedding')
tf.flags.DEFINE_string('validate_data_file', './data_bunch/cnn_non_stop_words_validate_bunch.dat', "get it's label to submmit")
tf.flags.DEFINE_integer("num_classes", 3, "Number of labels for data")
tf.flags.DEFINE_float('test_sample_percentage', 0.2, 'Percentage of the training data to use for testing')
tf.flags.DEFINE_string('word2vec_model_path', './word2vec/trained_word2vec.model',"path of word2vec model, use it to representate chinese data")
# Model hyperparameters
tf.flags.DEFINE_integer("embedding_dim", 400, "Dimensionality of character embedding (default: 400)")
tf.flags.DEFINE_string("filter_sizes", "3,4,5,6", "Comma-spearated filter sizes (default: '3,4,5')")
tf.flags.DEFINE_integer("num_filters", 128, "Number of filters per filter size (default: 128)")
tf.flags.DEFINE_float("dropout_keep_prob", 0.5, "Dropout keep probability (default: 0.5)")
tf.flags.DEFINE_float('learning_rate_basic', 0.8, "basic learning rate for dynamic modify learning rate")
tf.flags.DEFINE_float('learning_rate_decay', 0.99, "learning rate decay")
# Training paramters
tf.flags.DEFINE_integer("batch_size", 128, "Batch Size (default: 64)")
tf.flags.DEFINE_integer("num_epochs", 99999, "Number of training epochs (default: 200)")
tf.flags.DEFINE_integer("evaluate_every", 100, "Evalue model on dev set after this many steps (default: 100)")
tf.flags.DEFINE_integer("checkpoint_every", 100, "Save model after this many steps (defult: 100)")
tf.flags.DEFINE_integer("num_checkpoints", 5, "Number of checkpoints to store (default: 5)")
# Misc parameters
tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")
# Parse parameters from commands
FLAGS = tf.flags.FLAGS

# Loading data for training, validating and testing
train_data = data_helper.read_bunch(FLAGS.train_data_file)
train_label = data_helper.read_bunch(FLAGS.train_label_file)
# unlabel_data = data_helper.read_bunch(FLAGS.unlabel_data_file)
# validate_data = data_helper.read_bunch(FLAGS.validate_data_file)
# extract the data of needing to predict and submmit
# id_validate = validate_data.news_id
# x_validate = validate_data.news_words_jieba

# Fix the length of every sentence
sequence_length = 1657

# first: convert the string data to word vectors
x = data_helper.sentence2vector(train_data.news_words_jieba,length_per_sequence=sequence_length,word2vec_model_path=FLAGS.word2vec_model_path)
y = train_label.news_pic_label_one_hot
print('number of samples is :',len(x))
print('length of every sentence is :',len(x[0]))

# release memmory: delete some nouseful data
del train_data, train_label

# second: split training data into training and testing (1-FLAGS.test_sample_percentage)/test_sample_percentage ration
print('split training data into training set and testing set ...')
x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=FLAGS.test_sample_percentage, random_state=42)

# third: train textcnn model
# 用预处理得到的数据训练 TextCnn 模型
print("textcnn model training ...")
# Training
# =======================================================
with tf.Graph().as_default():
    session_conf = tf.ConfigProto(
        allow_soft_placement = FLAGS.allow_soft_placement,
        log_device_placement = FLAGS.log_device_placement)

    with tf.Session(config = session_conf) as sess:
        cnn = textcnn(
        sequence_length = sequence_length,
        num_classes = FLAGS.num_classes,
        embedding_size = FLAGS.embedding_dim,
        filter_sizes = list(map(int, FLAGS.filter_sizes.split(","))),
        num_filters = FLAGS.num_filters)

        # Define Training procedure
        global_step = tf.Variable(0, name="global_step", trainable=False)
        learning_rate = tf.train.exponential_decay(FLAGS.learning_rate_basic,
                                           global_step, len(x_train)/ FLAGS.batch_size,
                                           FLAGS.learning_rate_decay) 
        train_op = tf.train.AdamOptimizer(learning_rate).minimize(cnn.loss,global_step=global_step)

        saver = tf.train.Saver(tf.global_variables(), max_to_keep=FLAGS.num_checkpoints)
        # Initialize all variables
        sess.run(tf.global_variables_initializer())

        def train_step(x_batch, y_batch):
            """
            A single training step
            """
            feed_dict = {
              cnn.input_x: x_batch,
              cnn.input_y: y_batch,
              cnn.dropout_keep_prob: FLAGS.dropout_keep_prob
            }
            _, step, loss, accuracy, y_value = sess.run(
                [train_op, global_step, cnn.loss, cnn.accuracy, cnn.predictions],
                feed_dict)
            time_str = datetime.datetime.now().isoformat()
            if step % 50 ==0:
                print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))
                print('predictions on x_batch is \n',y_value)

        def test_step(x_batch, y_batch):
            """
            Evaluates model on a testing set
            """
            feed_dict = {
              cnn.input_x: x_batch,
              cnn.input_y: y_batch,
              cnn.dropout_keep_prob: 1.0
            }
            step, loss, accuracy = sess.run(
                [global_step, cnn.loss, cnn.accuracy],
                feed_dict)
            time_str = datetime.datetime.now().isoformat()
            print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))

        # Generate batches
        batches = data_helper.batch_iter(
            list(zip(x_train, y_train)), FLAGS.batch_size, FLAGS.num_epochs)

        # Training loop. For each batch ...
        for batch in batches:
            x_batch, y_batch = zip(*batch)
            train_step(x_batch, y_batch)
            current_step = tf.train.global_step(sess, global_step)
            # if current_step % FLAGS.evaluate_every == 0:
            #     print("\nEvaluation on testing set:")
            #     x_test, y_test =  zip(*np.array(list(zip(x_test, y_test))))
            #     test_step(x_test, y_test)
            #     print("")
            # if current_step % FLAGS.checkpoint_every == 0:
            #     path = saver.save(sess, './checkpoints/textcnn_model.ckpt', global_step=current_step)
            #     print("Saved model checkpoint to {}\n".format(path))






