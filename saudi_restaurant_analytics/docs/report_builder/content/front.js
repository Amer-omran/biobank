module.exports = (K, X) => {
  const { P } = K;
  const plainTitle = (t) => new X.Paragraph({ pageBreakBefore: true, alignment: X.AlignmentType.CENTER, spacing: { after: 240 },
    children: [new X.TextRun({ text: t, bold: true, italics: true, underline: {}, size: 32 })] });
  return [
    X.chapterTitle("Abstract"),
    P("Restaurants in Saudi Arabia receive thousands of online reviews on platforms such as Google Maps, most of them written in Saudi and Gulf dialects. These reviews contain valuable feedback about food, prices, portion sizes, service, delivery, cleanliness and atmosphere, but they are too numerous and too informal to be read and summarised by hand. This project designs, implements and evaluates a local, Arabic, right-to-left web platform that applies artificial intelligence to restaurant reviews in order to measure customer sentiment, identify the aspects customers praise or criticise, and extract the dishes they mention."),
    P("The core of the platform is an interpretable, lexicon- and rule-based aspect-based sentiment analyser built for Modern Standard Arabic and Saudi dialect. It handles negation (for example «مو حلو» and «ماعجبني»), intensifiers, contrast clauses introduced by «بس» and «لكن», implicit aspects and aspect-dependent words, and it reports a confidence score together with flags for mixed and uncertain results. A dictionary-based extractor recognises 57 Saudi and international dishes and 154 spelling variants without ever inventing a dish that is not mentioned. A TF-IDF and logistic-regression model built with scikit-learn serves as a machine-learning baseline. The platform stores data in SQLite, presents interactive dashboards built with Streamlit and Plotly, and exports reports to Excel and Arabic PDF."),
    P("The system was developed and evaluated on AQTE, a public dataset of 14,783 real Google Maps reviews of 774 restaurants across Saudi Arabia, annotated with 63,620 aspect-sentiment-quote triplets. The lexicon was improved over four versions using a development sample of 2,000 reviews drawn only from the training split; aspect-detection F1 on this sample rose from 0.775 to 0.814, and the sentiment of correctly detected aspects was right in about 90% of cases. On the held-out test split, the final lexicon-based analyser achieved [[final Accuracy]] accuracy and [[final Macro-F1]] macro-F1 for overall sentiment against a majority-class baseline of [[baseline Macro-F1]], and an aspect-detection F1 of [[final aspect F1]]; the scikit-learn baseline achieved [[sklearn Macro-F1]] macro-F1. The neutral class and the rarely mentioned delivery and quantity aspects remain the main weaknesses."),
    P("The results show that a transparent, dialect-aware lexicon approach can give restaurant owners and researchers reliable, explainable insight into customer opinion without paid cloud services, while the evaluation framework provides a reproducible basis for comparing future models."),
    P("**Keywords:** sentiment analysis; aspect-based sentiment analysis; Arabic natural language processing; Saudi dialect; restaurant reviews; lexicon-based methods; Streamlit."),

    X.chapterTitle("Acknowledgments"),
    P("First and foremost, I thank Allah for giving me the strength, patience and knowledge to complete this project."),
    P("I would like to express my sincere gratitude to my supervisor, **Dr. Baha Eldin Hamouda**, for his guidance, encouragement and valuable feedback throughout every stage of this work. His comments on the research questions and the evaluation design helped shape the project into its final form."),
    P("I am also grateful to the faculty and staff of the Department of Information Technology at Gulf Colleges for the knowledge and support they provided during my years of study."),
    P("I thank the authors of the AQTE dataset for making their annotated collection of Saudi restaurant reviews publicly available, and the open-source community behind Python, scikit-learn, Streamlit and the other tools used in this project."),
    P("Finally, I owe special thanks to my family for their continuous support, patience and encouragement."),

    plainTitle("Table of Contents"),
    new X.TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-2" }),
    plainTitle("List of Figures"),
    new X.TableOfContents("List of Figures", { hyperlink: true, stylesWithLevels: [new X.StyleLevel("Figure Caption", 1)] }),
    plainTitle("List of Tables"),
    new X.TableOfContents("List of Tables", { hyperlink: true, stylesWithLevels: [new X.StyleLevel("Table Caption", 1)] }),
  ];
};
