#!/usr/bin/python3

# ===========================
# ===== Import Packages =====
# ===========================
import pandas as pd
from tqdm import tqdm

import snscrape.modules.twitter as sntwitter

import re, string
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation

import pyLDAvis
import pyLDAvis.sklearn

from wordcloud import WordCloud
import matplotlib.pyplot as plt

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud import storage
from google.oauth2 import service_account

from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

### Connect Database
cred = credentials.Certificate("project-nlp-9b41d-firebase-adminsdk-w4jxt-038c435e97.json")
firebase_admin.initialize_app(cred,{
    'storageBucket': 'project-nlp-9b41d.appspot.com'})
db = firestore.client()  # this connects to our Firestore database
credentials = service_account.Credentials.from_service_account_file("project-nlp-9b41d-firebase-adminsdk-w4jxt-038c435e97.json")

# ===============================
# ===== Preprocess Function =====
# ===============================
# ___Remove Rubbish___
def clean_text(text): # credit to Fathur
    text = str(text)
    text = text.lower()
    text = re.sub("@[A-Za-z0-9_]+", "", text)  # Menghapus @<name> [mention twitter]
    text = re.sub("#\w+", "", text) # Menghapus hashtag #
    text = re.sub("\[.*?\]", "", text)  # Menghapus [string]
    text = re.sub("https?://\S+|www\.\S+", "", text)    # Menghapus link
    text = re.sub("<.*?>+", "", text)   # Menghapus <string>
    text = re.sub("[%s]" % re.escape(string.punctuation), "", text) # Menghapus tanda baca
    text = re.sub("\w*\d\w*", "", text) # Menghapus kata + angka ex: t0g3l
    text = re.sub("\d+", "", text)  # Menghapus kata diawali huruf ex: 45merdeka
    text = re.sub("amp", " ", text) # Menghapus &amp; pada kata
    text = re.sub("\s+", " ", text).strip() # Menghapus whitespace di antara kata
    text = text.replace("\n", " ")  # Menghapus tag newline
    text = " ".join(text.split())
    return text

# ___Stemming___
factory = StemmerFactory()
stemmer = factory.create_stemmer()

# ___Stopword___
factory_stop = StopWordRemoverFactory()
stopword = factory_stop.create_stop_word_remover()
dictionary = StopWordRemoverFactory().get_stop_words()
dictionary += ['yg', 'vs', 'cebong', 'utk', 'sy', 'jg', 'sbg', 'kpd', 'ttg', 'moga', 'lu', 'loe', 'doang', 'ak',
                'si', 'gak', 'dgn', 'dlm']

def removeStop(text):
    words = text.split(' ')
    stopped_words = [word for word in words if not word in dictionary]
    return ' '.join(stopped_words)


def sentiment():
    # ======================================================================================
    # ====================================== Scraping ======================================
    # ======================================================================================
    print('======================================================================================')
    print('====================================== Scraping ======================================')
    print('======================================================================================')
    print('\n')
    # ___jumlah scrap___
    hash_num_scrap = 500
    men_num_scrap = 1000
    print('Scraping', str(hash_num_scrap), 'hashtag tweet data')
    print('Scraping', str(men_num_scrap), 'hashtag tweet data')

    # ===========================
    # ===== Things to Query =====
    # ===========================
    calon = ['ganjar','prabowo','anies','ahy','rk']
    hashtags = ['ganjarpranowofor2024', 'prabowo', 'AniesPresiden2024', 'AHY', 'RidwanKamil']
    keywords = ['@ganjarpranowo', '@prabowo', '@aniesbaswedan', '@AgusYudhoyono', '@ridwankamil']

    # ====================================
    # ===== Scrap Hashtags + Mention =====
    # ====================================
    for user in range(len(hashtags)):
        print('\n' + 'Scraping #' + hashtags[user] + '...')
        # ___Hashtag scraper___
        tweets_list = []

        for i, tweet in enumerate(tqdm(sntwitter.TwitterHashtagScraper(hashtags[user]).get_items())):
            if i > hash_num_scrap:
                break
            tweets_list.append([tweet.id, tweet.date, tweet.user.username, tweet.content])

        tweets_df = pd.DataFrame(tweets_list, columns=['id', 'datetime', 'username', 'content'])

        # ___Cleaning, Stemming, Remove Stopwords, Remove Blank Text, Tokenize___
        print("Cleaning Process...")
        tweets_df['clean_text'] = tweets_df['content'].apply(lambda x: clean_text(x))
        tweets_df['clean_text'] = tweets_df['clean_text'].apply(lambda x: removeStop(x))
        tweets_df['clean_text_stem'] = tweets_df['clean_text'].apply(lambda x: stemmer.stem(x))
        tweets_df.replace("", float("NaN"), inplace=True) # Menghapus baris kosong setelah dihapus stopword
        tweets_df = tweets_df.dropna()
        tweets_df.reset_index(drop=True)

        print('\n' + 'Scraping mentions of ' + keywords[user] + '...')
        # ___User Profile scraper___
        user_mention_list = []

        for i, tweet in enumerate(tqdm(sntwitter.TwitterSearchScraper(keywords[user]).get_items())):
            if i > men_num_scrap:
                break
            user_mention_list.append([tweet.id, tweet.date, tweet.user.username, tweet.content])

        mentions_tweets_df = pd.DataFrame(user_mention_list, columns=['id', 'datetime', 'userName', 'content'])

        # ___Cleaning, Stemming, Remove Stopwords, Remove Blank Text, Tokenize___
        print("Cleaning Process...")
        mentions_tweets_df['clean_text'] = mentions_tweets_df['content'].apply(lambda x: clean_text(x))
        mentions_tweets_df['clean_text'] = mentions_tweets_df['clean_text'].apply(lambda x: removeStop(x))
        mentions_tweets_df['clean_text_stem'] = mentions_tweets_df['clean_text'].apply(lambda x: stemmer.stem(x))
        mentions_tweets_df.replace("", float("NaN"), inplace=True) # Menghapus baris kosong setelah dihapus stopword
        mentions_tweets_df = mentions_tweets_df.dropna()
        mentions_tweets_df.reset_index(drop=True)

        print("Scraping Selesai!")

        df_gabungan = pd.concat([tweets_df, mentions_tweets_df], ignore_index=True)
        df_gabungan['datetime'] = df_gabungan['datetime'].apply(lambda x: x.replace(tzinfo=None)+timedelta(hours=7))
        df_gabungan = df_gabungan[df_gabungan['datetime'] >= (datetime.now()-timedelta(days=2))]

        print('================================================================================================')
        print('====================================== Sentiment Analysis ======================================')
        print('================================================================================================')
        print('\n')

        # ========================
        # ===== Import Model =====
        # ========================
        pretrained= "mdhugol/indonesia-bert-sentiment-classification"

        model = AutoModelForSequenceClassification.from_pretrained(pretrained)
        tokenizer = AutoTokenizer.from_pretrained(pretrained)

        # ============================
        # ===== Model Definition =====
        # ============================
        sentiment_analysis = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)

        label_index = {'LABEL_0': 'positive', 'LABEL_1': 'neutral', 'LABEL_2': 'negative'}

        # ======================
        # ===== Prediction =====
        # ======================
        print('\n' + 'Processing {}....'.format(calon[user]))

        label = []

        for index, row in tqdm(df_gabungan.iterrows()):
            result = sentiment_analysis(row['clean_text'])
            status = label_index[result[0]['label']]
            label.append(status)

        df_gabungan['label'] = label

        path = f'database/sentiment_{calon[user]}.json'
        storage.Client(credentials=credentials).bucket(firebase_admin.storage.bucket().name).blob(path).download_to_filename(path)
        df_res = pd.read_json(path,orient='columns')

        df = pd.concat([df_res, df_gabungan], ignore_index=True)
        df = df.drop_duplicates()
        df.to_json(path,orient='columns')
        
        upload_blob(firebase_admin.storage.bucket().name, path, path)
        print("Data berhasil disimpan di database")

        print("Loading Data...")
        storage.Client(credentials=credentials).bucket(firebase_admin.storage.bucket().name).blob(path).download_to_filename(path)
        df_gabungan = pd.read_json(path,orient='columns')
        df_gabungan['datetime'] = df_gabungan['datetime'].apply(lambda x: x.replace(tzinfo=None))
        print("Slicing...")
        d14 = df_gabungan[df_gabungan['datetime'] >= (datetime.now()-timedelta(days=14))]
        d7 = df_gabungan[df_gabungan['datetime'] >= (datetime.now()-timedelta(days=7))]
        d1 = df_gabungan[df_gabungan['datetime'] >= (datetime.now()-timedelta(days=2))]
        print("Calculate....")
        df_name = [df_gabungan,d14,d7,d1]
        waktu = ['All time','14 Hari','7 Hari','Hari ini']
        hasil = {}
        for j in range(len(waktu)):
            sen = df_name[j]['label'].value_counts().to_dict()
            hasil[waktu[j]] = sen
            hasil[waktu[j]]['last_update'] = datetime.now()
        
        db.collection('Hasil Sentiment').document(calon[user]).set(hasil)
        print("Data berhasil disimpan di database")

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    credentials = service_account.Credentials.from_service_account_file("project-nlp-9b41d-firebase-adminsdk-w4jxt-038c435e97.json")
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

def wordcloud():
    # ___Join list as 1 string, and save wordcloud image___
    calon = ['ganjar','prabowo','anies','ahy','rk']
    for i in range(len(calon)):
        print('Processing {}....'.format(calon[i]))
        path = f'database/sentiment_{calon[i]}.json'
        storage.Client(credentials=credentials).bucket(firebase_admin.storage.bucket().name).blob(path).download_to_filename(path)
        df = pd.read_json(path,orient='columns')
        df['datetime'] = df['datetime'].apply(lambda x:x.replace(tzinfo=None))
        d14 = df[df['datetime'] >= (datetime.now()-timedelta(days=14))]
        d7 = df[df['datetime'] >= (datetime.now()-timedelta(days=7))]
        d1 = df[df['datetime'] >= (datetime.now()-timedelta(days=2))]

        df_name = [df,d14,d7,d1]
        waktu = ['All time','14 Hari','7 Hari','Hari ini']
        for j in tqdm(range(len(df_name))):
            print('Processing {}.....'.format(waktu[j]))
            pos = df_name[j][df_name[j]['label'] == 'positive']
            neg = df_name[j][df_name[j]['label'] == 'negative']
            neu = df_name[j][df_name[j]['label'] == 'neutral']

            df_sens = [pos,neu,neg]
            labels = ['pos', 'neu', 'neg']

            for branch in range(len(labels)):
                text_content = list(df_sens[branch]['clean_text_stem'])
                text_string = ''
                for elem in text_content:
                    text_string = ' '.join([text_string, str(elem)])
                
                # Colour
                if branch == 0:
                    wordcloud = WordCloud(background_color='white', width=2000, height=1000, colormap='summer').generate(text_string)
                elif branch == 1:
                    wordcloud = WordCloud(background_color='white', width=2000, height=1000).generate(text_string)
                else:
                    wordcloud = WordCloud(background_color='white', width=2000, height=1000, colormap='gist_heat').generate(text_string)

                # plot wordcloud
                plt.figure(figsize=(25,15))
                image = plt.imshow(wordcloud)

                # Hapus nilai axis
                plt.axis('off')
                plt.tight_layout(pad=0)
                path = 'wordcloud/{}/wordcloud_mention_{}_{}_{}.jpg'.format(calon[i],calon[i], waktu[j], labels[branch])
                plt.savefig(path)
                upload_blob(firebase_admin.storage.bucket().name, path, path)
        path = f'database/profile_{calon[i]}.json'
        storage.Client(credentials=credentials).bucket(firebase_admin.storage.bucket().name).blob(path).download_to_filename(path)
        df = pd.read_json(path,orient='columns')

        text_content = list(df['clean_text_stem'])

        text_string = ''
        for elem in text_content:
            text_string = ' '.join([text_string, str(elem)])

        wordcloud = WordCloud(background_color='white', width=2000, height=1000, colormap='summer').generate(text_string)

        # plot wordcloud
        plt.figure(figsize=(25,15))
        image = plt.imshow(wordcloud)

        # Hapus nilai axis
        plt.axis('off')
        plt.tight_layout(pad=0)
        path = 'wordcloud/{}/wordcloud_profile_{}.jpg'.format(calon[i],calon[i])
        plt.savefig(path)
        upload_blob(firebase_admin.storage.bucket().name, path, path)

    print('\n' + '========================= WORDCLOUD DONE =========================' + '\n')

def lda():
    # ======================================================================================
    # ====================================== Scraping ======================================
    # ======================================================================================
    print('======================================================================================')
    print('====================================== Scraping ======================================')
    print('======================================================================================')
    print('\n')
    # ___jumlah scrap___
    num_scrap = 20
    print('Scraping', str(num_scrap), 'tweet data')
    
    usernames = ['ganjarpranowo', 'prabowo', 'aniesbaswedan', 'AgusYudhoyono', 'ridwankamil']
    calon = ['ganjar','prabowo','anies','ahy','rk']
    # =======================================
    # ===== Scrap User Profile's Tweets =====
    # =======================================
    for user in range(len(usernames)):
        print('\n' + 'Scraping @' + usernames[user] + '...')
        # ___User Profile scraper___
        user_profile_list = []

        for i, tweet in enumerate(tqdm(sntwitter.TwitterUserScraper(usernames[user]).get_items())):
            if i > num_scrap:
                break
            user_profile_list.append([tweet.id, tweet.date, tweet.likeCount, tweet.content])

        user_tweets_df = pd.DataFrame(user_profile_list, columns=['id', 'datetime', 'likes', 'content'])

    # ___Cleaning, Stemming, Remove Stopwords, Remove Blank Text, Tokenize___
        print("Cleaning data...\n")
        user_tweets_df['clean_text'] = user_tweets_df['content'].apply(lambda x: clean_text(x))
        user_tweets_df['clean_text'] = user_tweets_df['clean_text'].apply(lambda x: removeStop(x))
        user_tweets_df['clean_text_stem'] = user_tweets_df['clean_text'].apply(lambda x: stemmer.stem(x))
        user_tweets_df.replace("", float("NaN"), inplace=True) # Menghapus baris kosong setelah dihapus stopword
        user_tweets_df = user_tweets_df.dropna()
        user_tweets_df.reset_index(drop=True)

        user_tweets_df['datetime'] = user_tweets_df['datetime'].apply(lambda x: x.replace(tzinfo=None)+timedelta(hours=7))
        user_tweets_df = user_tweets_df[user_tweets_df['datetime'] >= (datetime.now()-timedelta(days=2))]
        print('\n' + '========================= SCRAPE USER PROFILE DONE =========================' + '\n')

        path = f'database/profile_{calon[user]}.json'
        storage.Client(credentials=credentials).bucket(firebase_admin.storage.bucket().name).blob(path).download_to_filename(path)
        df_res = pd.read_json(path,orient='columns')
        df = pd.concat([df_res, user_tweets_df], ignore_index=True)
        df = df.drop_duplicates()

        df.to_json(path,orient='columns')
        upload_blob(firebase_admin.storage.bucket().name, path, path)

        print("Scrapping Done....")

        print("Processing LDA")

        print('=========================================================================================')
        print('====================================== Topic Model ======================================')
        print('=========================================================================================')
        print('\n')

        tfidf_vectorizer = TfidfVectorizer()
            # ___apply TF-IDF___
        dtm_tfidf = tfidf_vectorizer.fit_transform(list(df['clean_text_stem']))

        # ___apply LDA___
        lda_tfidf = LatentDirichletAllocation(n_components=10)
        lda_tfidf.fit(dtm_tfidf)

        # ___export HTML___

        data = pyLDAvis.sklearn.prepare(lda_tfidf, dtm_tfidf, tfidf_vectorizer)
        path = 'lda/lda_{}.html'.format(calon[user])
        pyLDAvis.save_html(data, path)
        upload_blob(firebase_admin.storage.bucket().name, path, path)


def main():
    sentiment()
    lda()
    wordcloud()    


