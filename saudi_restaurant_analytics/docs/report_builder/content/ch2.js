module.exports = (K, X) => {
  const { P, H2, H3, bullets, table } = K;
  return [
    X.chapterTitle("Chapter 2: Literature Review"),
    H2("2.1 Introduction"),
    P("This chapter reviews recent research (2021 to 2026) that underpins the project. It begins with the main concepts and levels of sentiment analysis, then compares the families of approaches: lexicon-based methods, classical machine learning, pre-trained language models and large language models. It then focuses on aspect-based sentiment analysis, the task this project implements, before turning to the challenges and resources of Arabic and Saudi-dialect sentiment analysis, including recent work on Saudi restaurant reviews. The chapter closes with evaluation practices, a summary of the related work and the research gap that motivates the project."),

    H2("2.2 Sentiment Analysis: Concepts and Levels"),
    P("Sentiment analysis is the automatic extraction of the positive or negative orientation that a writer expresses towards an object, such as a product, a service or a person (Jurafsky & Martin, 2026). In practice most systems classify the polarity of a text as positive, negative or neutral, and many also identify the target of the opinion."),
    P("Research distinguishes three levels of analysis (Zhang et al., 2023):"),
    bullets([
      "**Document level** assigns one polarity to a whole review. It assumes that the review expresses a single opinion about a single entity, which is rarely true of restaurant reviews.",
      "**Sentence level** assigns a polarity to each sentence. It is finer, but a sentence such as «الأكل لذيذ بس غالي» (the food is tasty but expensive) still contains two opinions about two different targets.",
      "**Aspect level** identifies each target (the aspect) and the sentiment expressed towards it. This is the level needed by restaurant owners, who want to know whether customers are unhappy with the food, the price or the service, not only whether a review is negative overall.",
    ]),
    P("Reviews of services such as hotels and restaurants are among the most common applications of sentiment analysis, because they are plentiful, explicitly evaluative and organised around a small number of well-understood aspects (Zhang et al., 2023)."),

    H2("2.3 Approaches to Sentiment Analysis"),
    H3("2.3.1 Lexicon-Based Methods"),
    P("Lexicon-based methods rely on a dictionary of words and phrases annotated with their polarity and, usually, a strength. The sentiment of a text is computed by combining the scores of the words it contains, with rules that modify those scores, for example for negation (Jurafsky & Martin, 2026). Their main strengths are interpretability, since every decision can be traced to specific words and rules, and independence from labelled training data. In a recent survey of Arabic sentiment analysis, Shi and Agrawal (2025) trace the field's move from lexicon-based methods towards deep learning, but note that sentiment lexicons remain valuable because they show how a classification was reached."),
    P("Their weaknesses are limited coverage of informal and domain-specific vocabulary, difficulty with context-dependent words (for example «بارد», cold, is negative for food but positive for a drink), and difficulty with sarcasm. These weaknesses are directly relevant to this project, because Saudi dialect contains many words that general lexicons do not cover."),
    H3("2.3.2 Machine-Learning Methods"),
    P("Supervised machine-learning methods learn a classifier from texts labelled with their sentiment. A standard and strong baseline represents each text with term frequency-inverse document frequency (TF-IDF) weights over words or n-grams and trains a linear classifier such as logistic regression (Jurafsky & Martin, 2026). Character n-grams are particularly useful for morphologically rich and noisy text, because they capture shared sub-word units even when spelling varies. Libraries such as scikit-learn provide tested implementations of these representations, classifiers and evaluation metrics (scikit-learn developers, 2026)."),
    P("Machine-learning models adapt to the vocabulary of their training data and can capture patterns that are hard to write as rules. However, they require labelled data from the target domain, they are less transparent than lexicon methods, and they classify a whole text unless they are designed specifically for aspect-level analysis."),
    H3("2.3.3 Pre-trained Language Models"),
    P("Pre-trained Transformer language models, fine-tuned on a specific task, have become the dominant approach in sentiment analysis research. Several such models were built for Arabic. ARBERT and MARBERT were pre-trained on large collections of Modern Standard and dialectal Arabic, the latter including social-media text, and were evaluated on a multi-dialect Arabic benchmark that includes sentiment tasks (Abdul-Mageed et al., 2021). The CAMeLBERT family was used to study how the variant of Arabic used in pre-training (Modern Standard, dialectal, classical or mixed) affects performance on different tasks, including sentiment analysis (Inoue et al., 2021)."),
    P("Fine-tuned Transformers generally achieve the strongest accuracy on benchmarks, but they require GPU resources for training and are harder to explain. For a project that must run locally and explain its decisions to non-technical users, these costs are significant."),
    H3("2.3.4 Large Language Models"),
    P("Large language models (LLMs) such as ChatGPT and GPT-4 can classify sentiment from instructions alone, without task-specific training. Their performance on Arabic is mixed. In a large evaluation over dozens of Arabic tasks, Khondaker et al. (2023) found that ChatGPT performed worse than much smaller models fine-tuned for Arabic on most tasks, and that both ChatGPT and GPT-4 performed worse on dialectal Arabic than on Modern Standard Arabic. Al-Thubaity et al. (2023), evaluating dialectal Arabic sentiment specifically, found that GPT-4 outperformed GPT-3.5 and Bard and rivalled the best fully supervised BERT-based model. LLMs therefore show promise, but they depend on paid or cloud services, raise privacy questions when customer data is sent to them, and are hard to audit. These are the reasons this project did not use them."),

    H2("2.4 Aspect-Based Sentiment Analysis"),
    P("Aspect-based sentiment analysis (ABSA) identifies the aspects of an entity that are discussed in a text and the sentiment expressed towards each of them. Zhang et al. (2023) describe ABSA in terms of four sentiment elements and the tasks built on them:"),
    bullets([
      "**Aspect term:** the words that refer to an aspect, such as «الخدمة» (the service) or «الكبسة» (the kabsa).",
      "**Aspect category:** a predefined category such as food quality or service.",
      "**Opinion term:** the words that express the opinion, such as «لذيذة» (tasty).",
      "**Sentiment polarity:** positive, negative or neutral.",
    ]),
    P("Single tasks extract one element, while compound tasks extract several together, such as aspect-category-sentiment pairs or triplets that also include the opinion text (Zhang et al., 2023). The AQTE dataset used in this project follows the compound view: each annotation is a triplet of aspect category, sentiment polarity and the verbatim opinion quote (bayandashnan, 2026). Zhang et al. (2023) also review the benchmark datasets of the field, in which restaurant reviews are one of the most common domains, and the shift from rule-based and feature-based methods to pre-trained language models."),
    P("Rule-based ABSA systems usually detect aspects with keyword lists and assign each opinion word to the nearest aspect. This proximity-based assignment within a clause is the strategy adopted by this project, extended with contrast-aware clause splitting and implicit aspects; for example, «غالي» (expensive) always refers to price."),

    H2("2.5 Arabic Sentiment Analysis"),
    H3("2.5.1 Challenges of Arabic"),
    P("Arabic has received much less sentiment-analysis research attention than English, and building robust Arabic models faces specific obstacles (Shi & Agrawal, 2025; Bensoltane & Zaki, 2022):"),
    bullets([
      "**Rich morphology.** Conjunctions, prepositions, the definite article and pronouns attach to words, so «وبالخدمة» contains the word «خدمة» with three prefixes, and «خدمتهم» contains it with a pronoun suffix that also changes the final ta marbuta «ة» into «ت».",
      "**Orthographic variation.** Writers use different forms of alef (أ، إ، آ، ا), interchange ta marbuta «ة» and ha «ه» and alef maqsura «ى» and ya «ي», and usually omit diacritics.",
      "**Dialects.** Online reviews are written mostly in regional dialects whose vocabulary and negation differ from Modern Standard Arabic. Saudi reviewers write «مو حلو» (not good), «زين» (good), «رهيب» (awesome), «ماصخ» (bland) and «وايد» (very).",
      "**Informal writing.** Letter elongation («حلووووو»), emojis, mixed Arabic and English, and creative spelling are common.",
      "**Sarcasm.** Sarcasm reverses the literal meaning of positive words. The WANLP 2021 shared task on sarcasm and sentiment detection in Arabic showed that sarcasm detection remains difficult even for fine-tuned Transformers (Abu Farha et al., 2021).",
    ]),
    H3("2.5.2 Saudi-Dialect Resources"),
    P("Freely available Saudi-dialect datasets and lexicons are scarcer than those for some other Arabic dialects. Almuqren and Cristea (2021) addressed this by building AraCust, a gold-standard corpus of Saudi-dialect tweets about telecommunications companies annotated for sentiment, and showed that a supervised classifier trained on it performed well. Their work illustrates the importance of domain and dialect: resources built for one domain or dialect often transfer poorly to another, which motivates domain-specific resources for restaurants."),
    H3("2.5.3 Saudi Restaurant Reviews"),
    P("Restaurant reviews in Saudi Arabia have recently become a research topic in their own right. Alharbi and Qamar (2022) applied deep learning to sentiment analysis of Arabic reviews of eateries in the Qassim region. AlMasaud and Al-Baity (2023) built AraMA and AraMAMS, corpora of Google Maps reviews of restaurants in Riyadh annotated for aspect-based sentiment analysis with four aspects (food, environment, service and price) and positive, negative, neutral and conflict polarities, with AraMAMS containing only reviews that express at least two different sentiments. They reported strong results for aspect-category detection with classical machine-learning models. AQTE extends this line of work with Google Maps reviews of 774 restaurants across Saudi Arabia, 29 aspect categories and verbatim opinion quotes for every annotation (bayandashnan, 2026)."),
    H3("2.5.4 Arabic Aspect-Based Sentiment Analysis"),
    P("Arabic ABSA has been studied mostly on hotel reviews from the SemEval-2016 benchmark. Al-Dabet et al. (2021) developed deep-learning models for aspect-category identification and aspect sentiment classification on this dataset. Abdelgwad et al. (2022) combined bidirectional GRU networks with convolutional and attention layers for opinion-target extraction and aspect polarity classification, reporting large improvements over baselines. In a review of Arabic ABSA, Bensoltane and Zaki (2022) classify existing studies by approach and identify the scarcity of annotated resources, the dominance of a few domains, and dialectal variation as the main open challenges. These findings support two design choices of this project: evaluation on a domain-specific Saudi dataset, and a lexicon with explicit Saudi-dialect vocabulary and rules."),

    H2("2.6 Evaluation of Sentiment Classifiers"),
    P("Sentiment classifiers are evaluated by comparing their output with human annotations using precision, recall and the F1 score for each class; with several classes, macro-averaging computes the measure for each class and averages the results, giving every class equal weight (Jurafsky & Martin, 2026). Accuracy alone is misleading when classes are imbalanced. Restaurant reviews are predominantly positive, so a trivial model that always predicts \"positive\" can reach a high accuracy while being useless. For this reason macro-F1 is the preferred summary measure, and results should be reported together with a majority-class baseline and a confusion matrix. Some benchmarks avoid the difficult neutral class altogether: the WANLP 2021 shared task ranked sentiment systems by the average F1 of the positive and negative classes only (Abu Farha et al., 2021)."),
    P("When results are aggregated to compare entities, for example the share of positive reviews for different restaurants, small samples produce unstable proportions. The Wilson score interval gives a confidence interval for a proportion that behaves well for small samples, and ranking by the lower bound of this interval prevents an entity with very few reviews from being ranked above one with many. This principle is used in the platform's restaurant comparison."),

    H2("2.7 Summary of Related Work"),
    ...table("Summary of related work (2021–2026) and its relevance to this project", ["Study", "Focus", "Relevance to this project"], [
      ["Zhang et al. (2023)", "Survey of ABSA tasks, methods and datasets", "Task definition; triplet view of ABSA"],
      ["Jurafsky & Martin (2026)", "Sentiment lexicons, TF-IDF, logistic regression, evaluation", "Foundations of the analyser, baseline and metrics"],
      ["Shi & Agrawal (2025)", "Survey of contemporary Arabic sentiment analysis", "Challenges of Arabic; value of lexicons for interpretability"],
      ["Bensoltane & Zaki (2022)", "Review of Arabic ABSA", "Open challenges: resources, domains, dialects"],
      ["Al-Dabet et al. (2021); Abdelgwad et al. (2022)", "Deep-learning Arabic ABSA on hotel reviews", "Arabic ABSA baselines"],
      ["Abdul-Mageed et al. (2021); Inoue et al. (2021)", "Arabic pre-trained language models (MARBERT, CAMeLBERT)", "Optional Transformer extension"],
      ["Khondaker et al. (2023); Al-Thubaity et al. (2023)", "Evaluation of ChatGPT, GPT-4 and Bard on Arabic tasks", "Why LLMs were not used as the core"],
      ["Abu Farha et al. (2021)", "Arabic sarcasm and sentiment shared task", "Explains a known limitation; neutral class in evaluation"],
      ["Almuqren & Cristea (2021)", "Saudi-dialect sentiment corpus (telecom)", "Saudi dialect resources"],
      ["Alharbi & Qamar (2022)", "Sentiment of Arabic eatery reviews, Qassim", "Saudi restaurant domain"],
      ["AlMasaud & Al-Baity (2023)", "ABSA corpora of Riyadh restaurant reviews (AraMA, AraMAMS)", "Closest prior work; Google Maps restaurant ABSA"],
      ["AQTE (bayandashnan, 2026)", "Saudi restaurant reviews with opinion triplets", "Evaluation dataset of this project"],
    ], [0.3, 0.4, 0.3]),

    H2("2.8 Research Gap"),
    P("Recent research shows that aspect-based sentiment analysis is well developed, that Arabic pre-trained models and LLMs are improving quickly, and that Saudi restaurant reviews have begun to receive attention. Three gaps remain that this project addresses:"),
    bullets([
      "**Transparency for dialectal restaurant reviews.** Recent Arabic ABSA work relies mainly on deep learning and LLMs, which are hard to explain. Few systems offer an interpretable, documented lexicon for Saudi restaurant language, with dish vocabulary and dialectal expressions such as «ماله طعم», «ما قصروا» and «يستاهل كل ريال».",
      "**Usability.** Research systems are usually models or scripts, not end-to-end applications that a restaurant owner can use in Arabic, with data import, dashboards, comparisons and reports, running locally without paid services.",
      "**Honest reporting.** Many tools report confident labels without evidence or uncertainty, and comparisons often ignore sample size. This project's analyser shows the supporting clause for every aspect decision, flags uncertain and mixed results, and refuses to rank restaurants with too few reviews.",
    ]),
    P("The following chapter describes the methodology used to build and evaluate a system that addresses these gaps."),
  ];
};
