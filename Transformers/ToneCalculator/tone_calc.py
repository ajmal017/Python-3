from datetime import datetime
from spacy.en import English
import pymongo
import pandas as pd
import os.path
import logging
import sys
import mongolog.dblogger as log


class ToneCalc(object):
    def __init__(self,
                 host='localhost',
                 port=27017,
                 db='python_import',
                 collection='earnings_call_Nas100_Broad_Manual_Update'):                         # earnings_transcript, earnings_call_Dow30_Broad, 
        self.client = pymongo.MongoClient(host=host, port=port)
        self.db = self.client[db]
        self.collection = self.db[collection]
        self.nlp = English()

        self.initialize_logging(db, host, port)
        self.initialize_dictionaries()

    def initialize_logging(self, db, host, port):
        mongo_handler = log.MongoHandler(host=host, port=port, db=db)
        mongo_handler.setLevel(level=logging.ERROR)
        logging.basicConfig(level=logging.INFO, format=mongo_handler.default_formatter_str)
        logging.getLogger().addHandler(mongo_handler)
        self.logger = logging.getLogger(__name__)

    def initialize_dictionaries(self):
        scriptpath = os.path.dirname(__file__)

        filename = os.path.join(scriptpath, 'words/henry_wordlist.xlsx')
        henry = pd.read_excel(filename)
        henry['Word'] = henry['Word'].str.lower()
        henry.reset_index()
        self.henry = henry

        filename = os.path.join(scriptpath, 'words/AFINN-111.txt')
        afinn = pd.read_csv(filepath_or_buffer=filename, sep='\t', header=None)
        afinn.rename(index=str, columns={0: "Word", 1: "Score"}, inplace=True)
        self.afinn = afinn

    def tokenize_simple(self, doc):
        return [tok.orth_.lower() for tok in doc]

    def tokenize_lemma(self, doc):
        return [tok.lemma_ for tok in doc if
                tok.pos_ in ["NOUN", "PROPN", "ADJ", "VERB"] and not tok.lemma_ == '-PRON-']

    def get_words(self, text):
        if text:
            doc = self.nlp(text)
            return self.tokenize_simple(doc), self.tokenize_lemma(doc)
        else:
            return [], []

    def get_first_value(self, dictionary, word):
        ser = dictionary[dictionary['Word'] == word]['Score']
        if len(ser) > 0:
            return ser.iloc[0]
        return 0

    def build_score_for_tokens(self, words, dictionary):
        score_pos, score_neg = 0, 0
        for word in words:
            temp_score = self.get_first_value(dictionary, word)
            if temp_score > 0:
                score_pos += temp_score
            elif temp_score < 0:
                score_neg += temp_score
        return score_pos, score_neg

    def process_words_with_dictionary(self, words, dictionary):
        score_pos, score_neg = self.build_score_for_tokens(words, dictionary)
        return {'positiveCount': int(score_pos), 'negativeCount': int(-score_neg)}

    def process(self, transcript):
        tokens, lemmas = self.get_words(transcript['rawText'])
        self.logger.info('{} tokens, {} lemmas'.format(len(tokens), len(lemmas)))
        henry_tokens = self.process_words_with_dictionary(tokens, self.henry)
        henry_lemmas = self.process_words_with_dictionary(lemmas, self.henry)

        afinn_tokens = self.process_words_with_dictionary(tokens, self.afinn)
        afinn_lemmas = self.process_words_with_dictionary(lemmas, self.afinn)

        return len(tokens), len(lemmas), henry_tokens, henry_lemmas, afinn_tokens, afinn_lemmas

    @log.error_logging_decorator
    def process_transcripts_and_save(self):
        # transcripts = self.collection.find({'publishDate':{'$gte':datetime(2017,3,31)}})
        # transcripts = self.collection.find({'tradingSymbol':'GOOGL'}, no_cursor_timeout=True).batch_size(30)
        transcripts = self.collection.find({"henry_tokens": {'$exists': False}},
                                           no_cursor_timeout=True).batch_size(30)

        for transcript in transcripts:
            self.logger.info('>>> Processing %s', transcript['url'])
            tokenSize, lemmaSize, henry_tokens, henry_lemmas, afinn_tokens, afinn_lemmas = \
                self.process(transcript)
            if isinstance(transcript['publishDate'], str):
                dt = datetime.strptime(transcript['publishDate'], '%Y-%m-%dT%H:%M:%SZ')
            else:
                dt = transcript['publishDate']
            date_number = (dt.year - 1900) * 10000 + (dt.month) * 100 + (dt.day)
            time_number = (dt.hour) * 10000 + (dt.minute) * 100 + (dt.second)
            self.collection.update_one(
                {'_id': transcript['_id']},
                {'$set': {'henry_tokens': henry_tokens,
                          'henry_lemmas': henry_lemmas,
                          'afinn_tokens': afinn_tokens,
                          'afinn_lemmas': afinn_lemmas,
                          'tokenSize': tokenSize,
                          'lemmaSize': lemmaSize,
                          'date_number': date_number,
                          'time_number': time_number}})
            self.logger.info(transcript['url'] + ' updated')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        tone_calc = ToneCalc(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
    else:
        tone_calc = ToneCalc()
    tone_calc.process_transcripts_and_save()
