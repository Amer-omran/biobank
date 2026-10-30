module.exports = (K, X) => {
  const { P, H2, H3, bullets, table } = K;
  return [
    X.chapterTitle("Chapter 2: Literature Review"),
    H2("2.1 Introduction"),
    P("This chapter reviews the research that underpins the project. It begins with the main concepts and levels of sentiment analysis, then compares the three families of approaches: lexicon-based methods, classical machine learning and deep learning. It then focuses on aspect-based sentiment analysis, the specific task this project implements, before turning to the particular challenges and resources of Arabic and Saudi-dialect sentiment analysis. The chapter closes with the evaluation practices used in the field, a summary of the related work and the research gap that motivates the project."),

    H2("2.2 Sentiment Analysis: Concepts and Levels"),
    P("Sentiment analysis, also called opinion mining, is the computational study of people's opinions, evaluations and attitudes towards entities such as products, services and organisations and towards their attributes (Liu, 2012; Pang & Lee, 2008). An opinion can be described by who holds it, what it is about, what it says and when it was expressed. In practice most systems focus on the polarity of the opinion, which is usually positive, negative or neutral, and on its target."),
    P("Research distinguishes three levels of analysis (Liu, 2012):"),
    bullets([
      "**Document level** assigns one polarity to a whole review. It assumes that the document expresses a single opinion about a single entity, which is rarely true of restaurant reviews.",
      "**Sentence level** assigns a polarity to each sentence. It is finer, but a sentence such as «الأكل لذيذ بس غالي» still contains two opinions about two different targets.",
      "**Aspect level** identifies each target (the aspect) and the sentiment expressed towards it. This is the level needed by restaurant owners, who want to know whether customers are unhappy with the food, the price or the service, not only whether a review is negative overall.",
    ]),
    P("Sentiment analysis has been applied to product reviews, social media, politics and finance. Reviews of services such as hotels and restaurants are a particularly common application because they are plentiful, explicitly evaluative and organised around a small number of well-understood aspects (Pontiki et al., 2014)."),

    H2("2.3 Approaches to Sentiment Analysis"),
    H3("2.3.1 Lexicon-Based Methods"),
    P("Lexicon-based methods rely on a dictionary of words and phrases annotated with their sentiment polarity and, usually, a strength. The sentiment of a text is computed by combining the scores of the words it contains, with rules that modify these scores. Taboada et al. (2011) showed that a carefully built lexicon combined with rules for intensification, negation and irrealis markers performs robustly across domains, and argued that such methods are transparent and do not depend on labelled training data. Hu and Liu (2004) used a lexicon of opinion words, expanded through synonym relations, to summarise customer reviews by product feature."),
    P("The main strengths of lexicon-based methods are interpretability, since every decision can be traced to specific words and rules, and independence from training data. Their weaknesses are limited coverage of informal and domain-specific vocabulary, difficulty with context-dependent words (for example «بارد», cold, is negative for food but positive for a drink), and difficulty with sarcasm. These strengths and weaknesses are directly relevant to this project, because Saudi dialect contains many words that general lexicons do not cover."),
    H3("2.3.2 Machine-Learning Methods"),
    P("Supervised machine-learning methods learn a classifier from texts labelled with their sentiment. Early influential work represented documents as bags of words and n-grams and trained classifiers such as Naive Bayes, support vector machines and logistic regression (Pang & Lee, 2008). The term frequency-inverse document frequency (TF-IDF) weighting scheme, which gives more weight to terms that are frequent in a document but rare in the collection, remains a standard and strong representation for text classification (Manning et al., 2008). Character n-grams are particularly useful for morphologically rich and noisy text, because they capture shared sub-word units even when spelling varies. Libraries such as scikit-learn make these models easy to build and evaluate (Pedregosa et al., 2011)."),
    P("Machine-learning models adapt to the vocabulary of their training data and can capture patterns that are hard to write as rules. However, they require labelled data from the target domain, they are less transparent than lexicon methods, and they typically classify a whole text rather than individual aspects unless they are designed specifically for ABSA."),
    H3("2.3.3 Deep Learning and Pre-trained Language Models"),
    P("Deep learning has become the dominant paradigm in sentiment analysis research. Recurrent and convolutional neural networks were followed by attention-based models, and more recently by pre-trained Transformer language models that are fine-tuned on a specific task (Zhang et al., 2018). For Arabic, AraBERT (Antoun et al., 2020) and the CAMeLBERT family (Inoue et al., 2021) are BERT-style models pre-trained on large Arabic corpora; Inoue et al. (2021) studied how the variant of Arabic used in pre-training, whether Modern Standard, dialectal, classical or a mixture, affects performance on different tasks, including sentiment analysis."),
    P("Fine-tuned Transformers generally achieve the strongest accuracy on benchmark datasets, but they require GPU resources for training, are harder to explain, and may transfer imperfectly to a new domain or dialect. For a graduation project that must run locally and explain its decisions to non-technical users, these costs are significant, which is why this project uses an interpretable lexicon-based analyser as its core, a classical machine-learning model as a baseline, and supports pre-trained Transformers only as an optional extension."),

    H2("2.4 Aspect-Based Sentiment Analysis"),
    P("Aspect-based sentiment analysis aims to identify the aspects of an entity that are discussed in a text and the sentiment expressed towards each of them (Schouten & Frasincar, 2016). It is usually decomposed into sub-tasks:"),
    bullets([
      "**Aspect term extraction:** finding the words that refer to an aspect, such as «الخدمة» (the service) or «الكبسة» (the kabsa).",
      "**Aspect category detection:** assigning the text to predefined categories such as FOOD#QUALITY or SERVICE#GENERAL.",
      "**Aspect sentiment classification:** deciding the polarity expressed towards each aspect.",
      "**Opinion or quote extraction:** identifying the exact span of text that expresses the opinion, which provides evidence for the decision.",
    ]),
    P("The SemEval shared tasks played a major role in standardising ABSA. SemEval-2014 Task 4 provided English restaurant and laptop reviews annotated with aspect terms, categories and polarities (Pontiki et al., 2014). SemEval-2016 Task 5 extended the task to several languages and domains, including Arabic hotel reviews (Pontiki et al., 2016). Restaurant reviews have remained one of the most common benchmark domains for ABSA."),
    P("Schouten and Frasincar (2016) survey ABSA methods and group them into dictionary-based, supervised machine-learning, unsupervised and hybrid approaches. Dictionary and rule-based approaches typically detect aspects with keyword lists and assign each opinion word to the nearest aspect, using syntactic or proximity rules. This proximity-based assignment within a clause is the strategy adopted by this project, extended with contrast-aware clause splitting and implicit aspects (for example «غالي», expensive, always refers to price)."),

    H2("2.5 Arabic Sentiment Analysis"),
    H3("2.5.1 Challenges of Arabic"),
    P("Arabic presents a set of well-documented challenges for NLP (Habash, 2010; Boudad et al., 2018):"),
    bullets([
      "**Rich morphology.** Conjunctions, prepositions, the definite article and pronouns attach to words, so «وبالخدمة» contains the word «خدمة» together with three prefixes, and «خدمتهم» contains it with a pronoun suffix that also changes the final ta marbuta «ة» into «ت».",
      "**Orthographic variation.** Writers use different forms of alef (أ، إ، آ، ا), interchange ta marbuta «ة» and ha «ه» and alef maqsura «ى» and ya «ي», and usually omit diacritics.",
      "**Diglossia and dialects.** Online reviews are written mostly in regional dialects whose vocabulary, negation and grammar differ from Modern Standard Arabic. Saudi reviewers write «مو حلو» (not good), «زين» (good), «رهيب» (awesome), «ماصخ» (bland) and «وايد» (very).",
      "**Informal writing.** Letter elongation («حلووووو»), emojis, mixed Arabic and English, and creative spelling are common.",
      "**Negation and sarcasm.** Negation can be a separate word («ما عجبني») or attached («ماعجبني»), and sarcasm reverses the literal meaning of positive words. Abu Farha and Magdy (2020) showed that sarcasm is common in Arabic social media and closely related to sentiment.",
    ]),
    H3("2.5.2 Arabic Sentiment Resources"),
    P("A number of resources have been developed for Arabic sentiment analysis. LABR is a large-scale dataset of Arabic book reviews with star ratings (Aly & Atiya, 2013). ASTD is a dataset of Arabic tweets annotated for sentiment (Nabil et al., 2015). HARD is a large dataset of Arabic hotel reviews (Elnagar et al., 2018). ElSahar and El-Beltagy (2015) built multi-domain Arabic resources for sentiment analysis, covering domains including restaurants, hotels, movies and products, together with domain lexicons. ArSenL is a large-scale Arabic sentiment lexicon (Badaro et al., 2014). These resources show both the feasibility of Arabic sentiment analysis and the importance of domain and dialect: a model or lexicon built for one domain or dialect often transfers poorly to another."),
    H3("2.5.3 Saudi-Dialect Sentiment Analysis"),
    P("Saudi dialect has received specific attention. Al-Twairesh et al. (2017) built AraSenTi-Tweet, a corpus of Saudi tweets annotated for sentiment, and highlighted the dialectal phenomena that make Saudi text difficult for systems built on Modern Standard Arabic. Assiri et al. (2018) proposed enhancements to a lexicon-based approach for Saudi dialect, showing that adding dialect-specific words and rules, including rules for negation and intensification, improves performance. These findings support the design choice of this project: a lexicon that combines Modern Standard Arabic with Saudi and Gulf vocabulary, with explicit rules for dialectal negation such as «مو», «مب» and «ما».")
    ,
    H3("2.5.4 Arabic Aspect-Based Sentiment Analysis"),
    P("Arabic ABSA research has been driven largely by the Arabic hotel reviews of SemEval-2016 (Pontiki et al., 2016). Al-Smadi et al. (2018) compared a deep recurrent neural network with a support vector machine trained on rich hand-crafted features for ABSA of Arabic hotel reviews. They found that the deep model was faster to train and use, while the feature-based support vector machine performed better on some sub-tasks. Restaurant reviews in Saudi dialect, by contrast, have had fewer public aspect-level resources. The AQTE dataset used in this project (bayandashnan, n.d.) addresses this need by providing Saudi restaurant reviews from Google Maps annotated with complete opinion triplets: an aspect category, a sentiment polarity and the verbatim quote that expresses the opinion."),

    H2("2.6 Evaluation of Sentiment Classifiers"),
    P("Sentiment classifiers are evaluated by comparing their output with human or curated annotations using precision, recall and the F1 score for each class (Sokolova & Lapalme, 2009). Accuracy alone is misleading when classes are imbalanced. Restaurant reviews are predominantly positive, so a trivial model that always predicts \"positive\" can reach a high accuracy while being useless. For this reason the macro-averaged F1 score, which gives each class equal weight, is the preferred summary measure, and results should be reported together with a majority-class baseline and a confusion matrix."),
    P("When results are aggregated to compare entities, for example the share of positive reviews for different restaurants, small samples produce unstable proportions. The Wilson score interval (Wilson, 1927) gives a confidence interval for a proportion that behaves well for small samples, and ranking by the lower bound of this interval prevents an entity with very few reviews from being ranked above one with many. This principle is used in the platform's restaurant comparison."),

    H2("2.7 Summary of Related Work"),
    ...table("Summary of related work and its relevance to this project", ["Study", "Focus", "Relevance to this project"], [
      ["Hu & Liu (2004)", "Feature-based summarisation of customer reviews with an opinion lexicon", "Lexicon-based aspect summarisation"],
      ["Taboada et al. (2011)", "Lexicon-based sentiment with intensification and negation rules", "Rule design: negation, intensifiers"],
      ["Pontiki et al. (2014, 2016)", "SemEval ABSA tasks; restaurant reviews; Arabic hotel reviews in 2016", "Task definition and aspect categories"],
      ["Schouten & Frasincar (2016)", "Survey of aspect-level sentiment analysis", "Proximity-based aspect assignment"],
      ["Aly & Atiya (2013); Nabil et al. (2015); Elnagar et al. (2018)", "Arabic sentiment datasets: books, tweets, hotels", "Shows the importance of domain-specific data"],
      ["ElSahar & El-Beltagy (2015)", "Multi-domain Arabic resources and lexicons", "Domain lexicons, including restaurants"],
      ["Al-Twairesh et al. (2017); Assiri et al. (2018)", "Saudi-dialect corpus; lexicon enhancement for Saudi dialect", "Dialect vocabulary and negation rules"],
      ["Al-Smadi et al. (2018)", "Arabic ABSA of hotel reviews: deep learning vs. SVM", "Arabic ABSA baselines"],
      ["Antoun et al. (2020); Inoue et al. (2021)", "Arabic pre-trained language models", "Optional Transformer extension"],
      ["Abu Farha & Magdy (2020)", "Arabic sarcasm and sentiment", "Explains a known limitation"],
      ["AQTE (bayandashnan, n.d.)", "Saudi restaurant reviews with opinion triplets", "Evaluation dataset of this project"],
    ], [0.3, 0.4, 0.3]),

    H2("2.8 Research Gap"),
    P("The literature shows that aspect-based sentiment analysis is mature for English restaurant reviews and that Arabic sentiment resources exist for several domains and dialects. Three gaps remain that this project addresses:"),
    bullets([
      "**Domain and dialect.** Few tools target Saudi restaurant reviews specifically, at the aspect level, with vocabulary for Saudi dishes and dialectal expressions such as «ماله طعم», «ما قصروا» and «يستاهل كل ريال».",
      "**Usability.** Research systems are usually scripts or models, not end-to-end applications that a restaurant owner can use in Arabic, with data import, dashboards, comparisons and reports.",
      "**Transparency and honest reporting.** Many tools report confident labels without evidence or uncertainty, and comparisons often ignore sample size. This project's analyser shows the supporting clause for every aspect decision, flags uncertain and mixed results, and refuses to rank restaurants with too few reviews.",
    ]),
    P("The following chapter describes the methodology used to build and evaluate a system that addresses these gaps."),
  ];
};
