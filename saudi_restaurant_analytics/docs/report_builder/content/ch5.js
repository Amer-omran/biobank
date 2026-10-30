module.exports = (K, X) => {
  const { P, H2, H3, bullets, table, figure } = K;
  const F = (t) => `[[${t}]]`;
  return [
    X.chapterTitle("Chapter 5: Results and Discussion"),
    P("This chapter summarises what the project delivered, reports the evaluation results on the AQTE dataset, answers the three research questions, discusses the errors and limitations of the analyser, and evaluates the project against its objectives."),

    H2("5.1 Project Summary"),
    P("The project delivered a complete, tested platform for analysing Arabic restaurant reviews. Its main components are an Arabic text-processing module, a lexicon- and rule-based aspect-based sentiment analyser for Modern Standard Arabic and Saudi dialect, a dictionary-based dish extractor, a scikit-learn baseline, a SQLite database with enforced integrity, an Arabic right-to-left web interface of eight pages, Excel and Arabic PDF reports, and a set of command-line tools for evaluation and error analysis on the AQTE dataset. The analyser was improved over four versions on training data only, frozen at version 1.3, and evaluated once on the held-out test split."),

    H2("5.2 Evaluation Results"),
    H3("5.2.1 What Customers Write About"),
    P("Before evaluating the models, the AQTE annotations themselves show which aspects customers write about. Figure 5.1 maps the 63,620 annotated opinions to the platform's aspects. Food quality dominates with 30,261 opinion mentions, followed by service with 11,985; price, ambiance and cleanliness follow at a distance; and quantity (1,110) and delivery (676) are rare. A further 9,720 opinions belong to general categories such as «المطعم» (the restaurant) and «التجربة» (the experience). In the training split, 65.5% of the opinions are positive (36,421), 25.2% negative (14,035) and 9.3% neutral (5,161)."),
    ...figure("fig_aqte_aspects.png", "Annotated opinion mentions per platform aspect in AQTE (training and test splits)", 5.2),
    P("This imbalance shapes everything that follows. The analyser has many examples of food and service language to learn from during development but very few of delivery and quantity, and a classifier that ignored the neutral class would lose little accuracy, which is why macro-F1 is the primary measure."),
    H3("5.2.2 Development Results"),
    P("On the development sample of 2,000 training reviews, the final lexicon (version 1.3) achieved an overall-sentiment accuracy of 0.820 and a macro-F1 of 0.614 against the AQTE opinions, compared with 0.703 and 0.275 for the majority-class baseline. Per class, F1 was 0.91 for positive, 0.74 for negative and 0.19 for neutral. Aspect detection reached a micro-averaged precision of 0.853, recall of 0.779 and F1 of 0.814, and the sentiment of correctly detected aspects was right in 89.9% of cases. Figure 5.2 shows aspect-detection F1 per aspect."),
    ...figure("fig_dev_aspects.png", "Aspect-detection F1 per aspect on the development sample (lexicon v1.3)", 5.2),
    H3("5.2.3 Final Results on the Test Split"),
    P(`The final evaluation was run once on the ${F("number")} reviews of the test split. Table 5.1 reports overall sentiment against the primary reference (AQTE opinions), and Table 5.2 against the secondary reference (star ratings).`),
    ...table("Overall sentiment on the test split against AQTE opinions", ["Model", "Accuracy", "Macro-F1", "F1 positive", "F1 negative", "F1 neutral"], [
      ["Majority baseline (always positive)", F("acc"), F("macro"), F("—"), "0.00", "0.00"],
      ["Lexicon analyser v1.3", F("acc"), F("macro"), F("pos"), F("neg"), F("neu")],
      ["scikit-learn (TF-IDF + logistic regression)", F("acc"), F("macro"), F("pos"), F("neg"), F("neu")],
    ], [0.34, 0.13, 0.13, 0.13, 0.14, 0.13]),
    ...table("Overall sentiment on the test split against star ratings", ["Model", "Accuracy", "Macro-F1"], [
      ["Majority baseline (always positive)", F("acc"), F("macro")],
      ["Lexicon analyser v1.3", F("acc"), F("macro")],
      ["scikit-learn (TF-IDF + logistic regression)", F("acc"), F("macro")],
    ], [0.5, 0.25, 0.25]),
    P("Table 5.3 reports aspect detection and aspect sentiment on the test split."),
    ...table("Aspect detection and aspect sentiment on the test split (lexicon v1.3)", ["Aspect", "Reference mentions", "Precision", "Recall", "F1", "Sentiment accuracy"], [
      ["Food quality", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["Price", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["Quantity", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["Service", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["Delivery", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["Cleanliness", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["Ambiance", F("n"), F("P"), F("R"), F("F1"), F("acc")],
      ["**All aspects (micro)**", "", F("P"), F("R"), F("F1"), F("acc")],
    ], [0.24, 0.16, 0.14, 0.14, 0.14, 0.18]),
    P(F("A sentence comparing test results with development results will be added here: whether the test results are close to the development results, which indicates that the lexicon did not over-fit the development sample.")),

    H2("5.3 Answers to the Research Questions"),
    H3("RQ1: Accuracy of the lexicon-based analyser"),
    P(`On the held-out test split the lexicon analyser reached a macro-F1 of ${F("value")} against the AQTE opinions, compared with ${F("value")} for the majority baseline, and an aspect-detection F1 of ${F("value")}. On the development sample, the sentiment of correctly detected aspects was right in about nine cases out of ten. The analyser is strong where language is frequent and explicit (food, price and service) and on clearly positive or negative reviews. It is weak on the neutral class and on rarely mentioned aspects (delivery and quantity). The answer to RQ1 is therefore that a transparent, dialect-aware lexicon analyser is accurate enough to be useful for positive, negative and frequent aspects, but its neutral judgements and its results for rare aspects should be read with caution.`),
    H3("RQ2: Lexicon versus machine learning"),
    P(F("This answer will be written from Table 5.1. If the scikit-learn model has a higher macro-F1: the supervised model, trained on about 12,900 labelled reviews, captures vocabulary the lexicon lacks, but it gives no aspect information and no explanation, so the two are complementary: the model for overall labels, the lexicon for aspects and evidence. If the lexicon is comparable or better: a carefully built lexicon can match a supervised baseline without any training data while remaining explainable.")),
    H3("RQ3: Aspects and dishes associated with satisfaction and complaints"),
    P("The annotations show that food is by far the most discussed aspect, followed by service (Figure 5.1). " + F("Insert from the platform, after analysing the training split: which aspects have the highest share of positive mentions (strengths), which have the highest share of negative mentions (complaints), and which dishes are mentioned most and with what sentiment. Present dish mentions as preference indicators, not sales.")),

    H2("5.4 Discussion"),
    H3("5.4.1 Why the Neutral Class Is Difficult"),
    P("The neutral class was the weakest in every measurement (F1 of about 0.2 on the development sample). Three factors explain this. First, neutral reviews are rare (about 8% of the development sample), so few errors cost a large share of the class. Second, the boundary between neutral and mildly positive is blurred in practice: «عادي» (ordinary) or «لا بأس» (not bad) can be read either way. Third, a review annotated as neutral overall often contains both praise and complaints that cancel out in the reference labels, while the analyser weights the clause after «بس» more heavily and therefore leans to one side. The confusion matrices show that most neutral reviews were predicted as positive. This difficulty is widely reported in sentiment analysis research and is a known limitation of lexicon methods."),
    H3("5.4.2 Rare Aspects"),
    P("Delivery and quantity had the lowest F1 because they have few examples and varied vocabulary. Delivery language often names applications or describes events («وصل بارد», it arrived cold) rather than using a fixed keyword, and words such as «يكفي» (enough) improved quantity recall but also produced false positives, lowering its precision. With more examples, or with a supervised aspect classifier, these aspects would likely improve."),
    H3("5.4.3 Other Sources of Error"),
    bullets([
      "**Sarcasm:** a sentence such as «يا سلام على السرعة» (what wonderful speed!) after a long wait is read literally as positive.",
      "**Implicit opinions:** statements of fact such as «ماعطوني الا بخمسة وانا كان ودي ب ٢٠» (they only gave me five when I wanted twenty) express a complaint without any opinion word.",
      "**Ambiguous words:** «الطلب» (the order) refers to service, delivery and food alike, so it was deliberately not used as an aspect keyword, which lowers recall slightly.",
      "**Reference labels:** the star rating is an approximate reference; customers often give five stars while complaining in the text, which is why it was used only as a secondary reference.",
    ]),
    H3("5.4.4 Lessons From the Development Process"),
    P("Two lessons stand out. First, systematic error analysis found real software defects, not only missing words: single-word phrases were never matched, and aspect words with pronoun suffixes were missed because of the ta marbuta change. Fixing them gave the largest single improvement in recall. Second, evaluation tools need the same scrutiny as models. The misread sentiment scale (Section 3.7.4) was detected only because a result was implausible, a negative class of size zero; the tool now prints the scale and the values it observed on every run. Both lessons were recorded in a change log and protected by regression tests."),

    H2("5.5 System Benefits"),
    bullets([
      "**Time saved:** thousands of reviews are analysed in seconds instead of being read by hand.",
      "**Actionable detail:** results by aspect and by dish show not only whether customers are satisfied, but with what.",
      "**Explainability:** every decision is backed by opinion words and the supporting clause, which builds trust and makes errors easy to spot.",
      "**Honest reporting:** uncertainty and mixed opinions are shown, comparisons show their sample sizes, and restaurants with too few reviews are not ranked.",
      "**Low cost, privacy and Arabic-first design:** the platform runs locally with free software, stores no personal identifiers, needs no cloud account, and is designed for Arabic and Saudi dialect from the start.",
      "**Reproducible research:** evaluation and error analysis are single commands, and every lexicon version is documented.",
    ]),

    H2("5.6 Challenges Faced During Development"),
    ...table("Challenges and how they were addressed", ["Challenge", "How it was addressed"], [
      ["The development environment could not access the Hugging Face website, so the dataset structure could not be inspected there", "No column names were assumed; the importer was made fully configurable; the dataset was inspected through screenshots of its viewer and files before any code relied on its structure"],
      ["The optional libraries had no prebuilt packages for the newest Python version on Windows", "Core functionality kept free of these libraries; the importer was extended to read Parquet and JSON so datasets can be used without them"],
      ["ReportLab does not shape Arabic or order it right to left", "Lines wrapped in logical order, then shaped with arabic-reshaper and reordered with python-bidi, using the Amiri font"],
      ["Mixed Arabic and Latin text displayed in the wrong order in diagrams", "Diagrams explicitly set to right-to-left direction and checked visually"],
      ["The sentiment scale of AQTE was initially misread", "Detected from an implausible result, corrected, documented and protected by automatic scale detection"],
      ["Dialectal and spelling variation", "Normalisation, prefix and suffix variants, ta marbuta restoration, squeezed forms for elongation, and iterative lexicon development"],
      ["Risk of over-fitting the lexicon to the test data", "Strict separation: development on training data only, test split frozen and used once"],
      ["21 duplicate reviews found when importing the training split", "De-duplication with an option to keep duplicates; the decision is documented and does not affect evaluation, which reads the original files"],
    ], [0.45, 0.55]),

    H2("5.7 Project Evaluation and Impact"),
    P("Table 5.5 evaluates the project against the objectives set in Chapter 1."),
    ...table("Achievement of the project objectives", ["Objective", "Status", "Evidence"], [
      ["1. Arabic text processing that keeps sentiment signals", "Achieved", "Section 3.3; 11 tests"],
      ["2. Aspect-based sentiment analyser for MSA and Saudi dialect", "Achieved", "Sections 3.4 and 5.2; 34 tests"],
      ["3. Dish extraction without invented dishes", "Achieved", "Section 3.5; 7 tests"],
      ["4. Machine-learning baseline and comparison", "Achieved", "Sections 3.6 and 5.3"],
      ["5. Relational database with integrity", "Achieved", "Section 4.5.3; 8 tests"],
      ["6. Arabic RTL interface and reports", "Achieved", "Section 4.6.3; 17 interface tests"],
      ["7. Evaluation on real annotated Saudi data", "Achieved", "Section 5.2; held-out test split"],
    ], [0.5, 0.15, 0.35]),
    P("The project's main impact is to show that Saudi restaurant reviews can be analysed at the aspect level with a transparent, low-cost and locally running system whose strengths and weaknesses are measured honestly on real data. For restaurant owners it offers a practical decision-support tool; for researchers it offers a reproducible evaluation framework and a documented dialect lexicon that can serve as a baseline for future models."),
  ];
};
