#!/usr/bin/python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

import sys
import os
from sklearn.externals import joblib
from scipy.sparse import csr_matrix


from bigram import Bigram, viterbi
from tools import sentenceIterator, featurizeSentence


class Tagger():
    def __init__(self, features, options):
        self._features = features
        self._dataSizes = options['dataSizes']
        self._lmw = options['lmw']
        print('loading transition model...', end='', file=sys.stderr, flush=True)
        self._transProbs = Bigram.getModelFromFile(options['bigramModelFileName'])
        print('done\nloading observation model...', end='', file=sys.stderr, flush=True)
        self._model = joblib.load('{0}.model'.format(options['modelFileName']))
        self._labelCounter = options['labelCounter']
        self._featCounter = options['featCounter']
        print('done\n', file=sys.stderr, flush=True)

    def tag_features(self, file_name):
        sen_feats = []
        senCount = 0
        for line in open(file_name, encoding='UTF-8'):
            line = line.strip()
            if len(line) == 0:
                senCount += 1
                tagging = self._tag_sen_feats(sen_feats)
                yield [[tag] for tag in tagging]
                sen_feats = []
                if senCount % 1000 == 0:
                    print('{0}...'.format(str(senCount)), end='', file=sys.stderr, flush=True)
            sen_feats.append(line.split())
        print('{0}...done'.format(str(senCount)), file=sys.stderr, flush=True)

    def tag_dir(self, dir_name):
        for fn in os.listdir(dir_name):
            print('processing file {0}...'.format(fn), end='', file=sys.stderr, flush=True)
            try:
                for sen, _ in self.tag_corp(open(os.path.join(dir_name, fn), encoding='UTF-8')):
                    yield sen, fn
            except:
                print('error in file {0}'.format(fn), file=sys.stderr, flush=True)

    def tag_corp(self, inputStream):
        senCount = 0
        for sen, comment in sentenceIterator(inputStream):
            senCount += 1
            senFeats = featurizeSentence(sen, self._features)
            bestTagging = self._tag_sen_feats(senFeats)
            # Add tagging to sentence
            taggedSen = [tok + [bestTagging[c]] for c, tok in enumerate(sen)]
            yield taggedSen, comment
            if senCount % 1000 == 0:
                print('{0}...'.format(str(senCount)), end='', file=sys.stderr, flush=True)
        print('{0}...done'.format(str(senCount)), file=sys.stderr, flush=True)

    def _getLogTagProbsByPos(self, senFeats):
        # Get Sentence Features translated to numbers and contexts in two steps
        featNumbers = [set([self._featCounter.getNoTag(feat) for feat in feats])
                       for feats in senFeats]
        invalidFeatNo = self._featCounter.featNumNotFound

        rows = []
        cols = []
        data = []
        for rownum, featNumberSet in enumerate(featNumbers):
            for featNum in featNumberSet:
                if featNum > invalidFeatNo:
                    rows.append(rownum)
                    cols.append(featNum)
                    data.append(1)
        contexts = csr_matrix((data, (rows, cols)),
                              shape=(len(featNumbers), self._featCounter.numOfFeats()),
                              dtype=self._dataSizes['dataNP'])
        logTagProbsByPos = [dict([(self._labelCounter.noToFeat[i], prob)
                   for i, prob in enumerate(probDist)])
                   for probDist in self._model.predict_log_proba(contexts)]
        return logTagProbsByPos

    def _tag_sen_feats(self, sen_feats):
        logTagProbsByPos = self._getLogTagProbsByPos(sen_feats)
        _, bestTagging = viterbi(self._transProbs, logTagProbsByPos,
                                 self._lmw)
        return bestTagging
