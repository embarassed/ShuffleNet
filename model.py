import tensorflow as tf
from layers import shufflenet_unit, conv2d, max_pool_2d, avg_pool_2d, dense, flatten


class ShuffleNet:
    """ShuffleNet is implemented here!"""

    def __init__(self, args):
        self.args = args
        self.X = None
        self.y = None
        self.logits = None
        self.is_training = None
        self.loss = None
        self.train_op = None
        self.accuracy = None
        self.y_out_argmax = None

        # A number stands for the num_groups
        # Output channels for conv1 layer
        self.output_channels = {'1': [144, 288, 576], '2': [200, 400, 800], '3': [240, 480, 960], '4': [272, 544, 1088],
                                '8': [384, 768, 1536], 'conv1': 24}

        self.__build()

    def __init_input(self):
        with tf.variable_scope('input'):
            # Input images
            self.X = tf.placeholder(tf.float32,
                                    [None, self.args.img_height, self.args.img_width,
                                           self.args.num_channels])
            # Classification supervision, it's an argmax. Feel free to change it to one-hot,
            # but don't forget to change the loss from sparse as well
            self.y = tf.placeholder(tf.int32, [None])
            # is_training is for batch normalization and dropout, if they exist
            self.is_training = tf.placeholder(tf.bool)

    def __stage(self, x, stage=2, repeat=3):
        if 2 <= stage <= 4:
            stage_layer = shufflenet_unit('stage' + str(stage) + '_1', x=x, w=None, num_groups=self.args.num_groups,
                                          group_conv_bottleneck=not (stage == 2),
                                          num_filters=self.output_channels[str(self.args.num_groups)][stage - 2],
                                          stride=(2, 2),
                                          fusion='concat', l2_strength=self.args.l2_strength, bias=self.args.bias,
                                          batchnorm_enabled=self.args.batchnorm_enabled,
                                          is_training=self.is_training)
            for i in range(1, repeat + 1):
                stage_layer = shufflenet_unit('stage' + str(stage) + '_' + str(i), x=stage_layer, w=None,
                                              num_groups=self.args.num_groups,
                                              group_conv_bottleneck=True,
                                              num_filters=self.output_channels[str(self.args.num_groups)][stage - 2],
                                              stride=(1, 1),
                                              fusion='add', l2_strength=self.args.l2_strength,
                                              bias=self.args.bias,
                                              batchnorm_enabled=self.args.batchnorm_enabled,
                                              is_training=self.is_training)
            return stage_layer
        else:
            raise ValueError("Stage should be from 2 -> 4")

    def __init_output(self):
        with tf.variable_scope('output'):
            self.loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=self.logits, labels=self.y, name='loss')
            self.train_op = tf.train.AdamOptimizer(learning_rate=self.args.learning_rate).minimize(self.loss)
            self.y_out_argmax = tf.arg_max(tf.nn.softmax(self.logits), output_type=tf.int32)
            self.accuracy = tf.reduce_mean(tf.reduce_mean(tf.cast(tf.equal(self.y, self.y_out_argmax), tf.float32)))

    def __build(self):
        self.__init_global_epoch()
        self.__init_input()
        conv1 = conv2d('conv1', x=self.X, w=None, num_filters=self.output_channels['conv1'], kernel_size=(3, 3),
                       stride=(2, 2), l2_strength=self.args.l2_strength, bias=self.args.bias,
                       batchnorm_enabled=self.args.batchnorm_enabled, is_training=self.is_training)
        max_pool = max_pool_2d(conv1, size=(3, 3), stride=(2, 2), name='max_pool')
        stage2 = self.__stage(max_pool, stage=2, repeat=3)
        stage3 = self.__stage(stage2, stage=3, repeat=7)
        stage4 = self.__stage(stage3, stage=4, repeat=3)
        global_pool = avg_pool_2d(stage4, size=(7, 7), stride=(1, 1), name='global_pool')
        flattened = flatten(global_pool)
        self.logits = dense('fc', flattened, w=None, output_dim=1000, l2_strength=self.args.l2_strength,
                            bias=self.args.bias,
                            is_training=self.is_training)
        self.__init_output()

    def __init_global_epoch(self):
        """
        Create a global epoch tensor to totally save the process of the training
        :return:
        """
        with tf.variable_scope('global_epoch'):
            self.global_epoch_tensor = tf.Variable(-1, trainable=False, name='global_epoch')
            self.global_epoch_input = tf.placeholder('int32', None, name='global_epoch_input')
            self.global_epoch_assign_op = self.global_epoch_tensor.assign(self.global_epoch_input)

    def __init_global_step(self):
        """
        Create a global step variable to be a reference to the number of iterations
        :return:
        """
        with tf.variable_scope('global_step'):
            self.global_step_tensor = tf.Variable(0, trainable=False, name='global_step')
            self.global_step_input = tf.placeholder('int32', None, name='global_step_input')
            self.global_step_assign_op = self.global_step_tensor.assign(self.global_step_input)