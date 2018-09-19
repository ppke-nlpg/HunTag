#!/usr/bin/python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

import sys
import os
from sklearn.externals import joblib
from scipy.sparse import csr_matrix

from tools import sentence_iterator, featurize_sentence, use_featurized_sentence, BookKeeper, feature_names_to_indices


class Tagger:
    def __init__(self, features, trans_model, options):
        self._features = feature_names_to_indices(features, options['field_names'])
        self._tag_field = options['field_names'][options['tag_field']]
        self._data_sizes = options['data_sizes']
        self._trans_probs = trans_model
        print('loading observation model...', end='', file=sys.stderr, flush=True)
        self._model = joblib.load('{0}'.format(options['modelFileName']))
        self._feat_counter = BookKeeper(options['featCounterFileName'])
        self._label_counter = BookKeeper(options['labelCounterFileName'])
        print('done', file=sys.stderr, flush=True)

    def _get_tag_probs_by_pos(self, feat_numbers):
        rows, cols, data = [], [], []
        for rownum, featNumberSet in enumerate(feat_numbers):
            for featNum in featNumberSet:
                rows.append(rownum)
                cols.append(featNum)
                data.append(1)
        contexts = csr_matrix((data, (rows, cols)), shape=(len(feat_numbers), self._feat_counter.num_of_names()),
                              dtype=self._data_sizes['data_np'])
        tagprobs_by_pos = [{self._label_counter.no_to_name[i]: prob for i, prob in enumerate(prob_dist)}
                           for prob_dist in self._model.predict_proba(contexts)]
        return tagprobs_by_pos

    @staticmethod
    def _add_tagging_normal(_, best_tagging, __):
        return [[label] for label in best_tagging]

    @staticmethod
    def _add_tagging_featurized(sent, best_tagging, tag_index):
        for tok, label in zip(sent, best_tagging):
            tok.insert(tag_index, label)
        return sent

    def tag_by_feat_number(self, sen, feat_numbers, add_tagging, tag_index):
        best_tagging = self._trans_probs.tag_sent(self._get_tag_probs_by_pos(feat_numbers))
        return add_tagging(sen, best_tagging, tag_index)  # Add tagging to sentence

    @staticmethod
    def _print_features(_, __, feat_numbers, featno_to_name, ___):
        return [[featno_to_name[featNum].replace(':', 'colon') for featNum in featNumberSet]
                for featNumberSet in feat_numbers]

    def tag_corp(self, input_stream, featurized_data=False, print_features=False):
        if featurized_data:
            featurize_sentence_fun = use_featurized_sentence
            format_output = self._add_tagging_featurized
            tag_fun = self.tag_by_feat_number
        else:
            featurize_sentence_fun = featurize_sentence
            if print_features:  # print features
                format_output = self._feat_counter.no_to_name
                tag_fun = self._print_features
            else:               # tag sentences
                format_output = self._add_tagging_normal
                tag_fun = self.tag_by_feat_number

        get_no_tag = self._feat_counter.get_no_tag
        sen_count = 0
        for sen, comment in sentence_iterator(input_stream):
            sen_count += 1
            sen_feats = featurize_sentence_fun(sen, self._features)
            # Get Sentence Features translated to numbers and contexts in two steps
            feat_numbers = [{get_no_tag(feat) for feat in feats if get_no_tag(feat) is not None} for feats in sen_feats]

            yield tag_fun(sen, feat_numbers, format_output, self._tag_field), comment

            if sen_count % 1000 == 0:
                print('{0}...'.format(sen_count), end='', file=sys.stderr, flush=True)
        print('{0}...done'.format(sen_count), file=sys.stderr, flush=True)

    def tag_dir(self, dir_name):
        for fn in os.listdir(dir_name):
            print('processing file {0}...'.format(fn), end='', file=sys.stderr, flush=True)
            with open(os.path.join(dir_name, fn), encoding='UTF-8') as fh:
                field_names = {name: i for i, name in enumerate(fh.readline().strip().split())}
                self._features = feature_names_to_indices(self._features, field_names)
                for sen, _ in self.tag_corp(fh):
                    yield sen, fn

    def print_weights(self, n=100, output_stream=sys.stdout):
        coefs = self._model.coef_
        labelno_to_name = self._label_counter.no_to_name
        featno_to_name = self._feat_counter.no_to_name
        sorted_feats = sorted(featno_to_name.items())
        for i, label in sorted(labelno_to_name.items()):
            columns = ['{0}:{1}'.format(w, feat) for w, (no, feat) in sorted(zip(coefs[i, :], sorted_feats),
                                                                             reverse=True)]
            print('{0}\t{1}'.format(label, '\t'.join(columns[:n])), file=output_stream)  # Best
            # Worst -> Negative correlation
            print('{0}\t{1}'.format(label, '\t'.join(sorted(columns[-n:], reverse=True))), file=output_stream)
