#! /usr/bin/env python
# coding:utf-8


if __name__ == "__main__":
    import argparse
    from seq2seq import train_decoder
    from util import load_dictionary, load_sentence
    import configparser
    import os
    from chainer import serializers
    from gensim.models import word2vec
    import logging
    import relu_rnn

    logging.basicConfig(
        format='%(asctime)s : %(levelname)s : %(message)s',
        level=logging.INFO
    )

    # GPU config
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', metavar='config_file', type=str,
                        help='config file')
    parser.add_argument('--gpu', '-g', default=-1, type=int,
                        help='GPU ID (negative value indicates CPU)')
    parser.add_argument('--type', '-t', default="relu", type=str,
                        help='GPU ID (negative value indicates CPU)')
    args = parser.parse_args()
    gpu_flag = args.gpu if args.gpu >= 0 else -1

    config_file = args.config_file
    parser_config = configparser.ConfigParser()
    parser_config.read(config_file)
    config = parser_config["CONFIG"]
    # config["SEPARATOR"] = bytes(
    #     config["DEFAULT"]["SEPARATOR"], "utf-8"
    # ).decode("unicode_escape")

    # files
    encoder_model_dir = config["encoder_model_dir"]
    decoder_model_dir = config["decoder_model_dir"]

    # 辞書
    if os.path.exists(config["dict_file"]):
        dictionary = load_dictionary(config["dict_file"])
    else:
        from seq2seq import create_dictionary
        dictionary = create_dictionary(
            [config["sent_file"],
             ],
            min_freq=int(config["min_freq"])
        )
        dictionary.save(config["dict_file"])

    # Prepare encoder RNN model
    dim = len(dictionary.keys())
    model_type = args.type
    if model_type == "relu":
        encoder_model = relu_rnn.Classifier(
            relu_rnn.ReLURNN(
                embed_dim=dim,
                n_units=int(config["n_units"]),
                gpu=args.gpu
            )
        )
        decoder_model = relu_rnn.Classifier(
            relu_rnn.ReLURNN(
                embed_dim=dim,
                n_units=int(config["n_units"]),
                gpu=args.gpu
            )
        )
    elif model_type == "lstm":
        import lstm
        encoder_model = lstm.Classifier(
            lstm.LSTM(
                embed_dim=dim,
                n_units=int(config["n_units"]),
                gpu=args.gpu
            )
        )
        decoder_model = lstm.Classifier(
            lstm.LSTM(
                embed_dim=dim,
                n_units=int(config["n_units"]),
                gpu=args.gpu
            )
        )
    else:
        raise Exception("model argment should be relu or lstm")

    # load model
    init_encoder_model_name = os.path.join(
        encoder_model_dir,
        "model.npz"
    )
    if os.path.exists(init_encoder_model_name):
        serializers.load_npz(init_encoder_model_name, encoder_model)
        print("load encoder model {}".format(init_encoder_model_name))
    else:
        raise Exception("learn encoder model first")

    init_decoder_model_name = os.path.join(
        decoder_model_dir,
        "model.npz"
    )
    if os.path.exists(init_decoder_model_name):
        serializers.load_npz(init_decoder_model_name, decoder_model)
        print("load decoder model {}".format(init_decoder_model_name))
    else:
        import numpy as np
        print("learning word2vec model")
        word2vec_model = word2vec.Word2Vec(
            load_sentence(config["sent_file"]),
            size=int(config["n_units"]),
            window=5,
            min_count=1,
            workers=4
        )
        word2vec_model.save("word2vec.model")
        print("initializing word embedding by word2vec")
        initial_W = np.array([
            word2vec_model[dictionary[wid]]
            if dictionary[wid] in word2vec_model
            else np.array(
                [np.random.random() for _ in range(
                    int(config["n_units"]))
                 ],
                dtype=np.float32
            )
            for wid in range(dim)],
            dtype=np.float32
        )
        not_found_words = []
        for wid in range(dim):
            if dictionary[wid] not in word2vec_model:
                not_found_words.append(dictionary[wid])
        print("{} are not found in word2vec model".format(not_found_words))
        decoder_model.predictor.set_word_embedding(initial_W)
        print(initial_W)

    train_decoder(
        encoder_model,
        decoder_model,
        dictionary,
        config["conv_file"],
        decoder_model_dir,
        epoch_size=int(config["epoch_size"]),
        batch_size=int(config["batch_size"]),
        dropout=bool(config["dropout"]),
        gpu=gpu_flag
    )
