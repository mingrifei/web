import nltk
import jieba,math
import jieba.analyse
from jieba import analyse
from sklearn import feature_extraction
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
#深蓝词库转换
jieba.load_userdict('userdict.txt')
raw=open(u'rhtj.txt',encoding='utf-8',errors='ignore').read()
#tokens = nltk.word_tokenize(raw)
#print(tokens)
a=jieba.analyse.extract_tags(raw, topK=20, withWeight=False, allowPOS=('ns','n','vn','v'))
print(a)

str_jing1=jieba.cut(raw,cut_all=False)
print('load_userdict后:'+"/".join(str_jing1))
'''
# 基于TextRank算法进行关键词抽取
keywords =analyse.textrank(raw)
# 输出抽取出的关键词
for keyword in keywords:
    print(keyword + "/")
'''
def tfidf_keywords():
    # 00、读取文件,一行就是一个文档，将所有文档输出到一个list中
    corpus = []
    for line in open(u'rhtj.txt',encoding='utf-8').readlines():
        corpus.append(line)

    # 01、构建词频矩阵，将文本中的词语转换成词频矩阵
    vectorizer = CountVectorizer()
    # a[i][j]:表示j词在第i个文本中的词频
    X = vectorizer.fit_transform(corpus)
    print (X)  # 词频矩阵

    # 02、构建TFIDF权值
    transformer = TfidfTransformer()
    # 计算tfidf值
    tfidf = transformer.fit_transform(X)

    # 03、获取词袋模型中的关键词
    word = vectorizer.get_feature_names()

    # tfidf矩阵
    weight = tfidf.toarray()

    # 打印特征文本
    print (len(word))
    for j in range(len(word)):
        print (word[j])

    # 打印权重
    for i in range(len(weight)):
        for j in range(len(word)):
            print (weight[i][j])
            # print '\n'
#tfidf_keywords()