module.exports = (K, X) => {
  const { P, H2, bullets, numbers, table } = K;
  return [
    X.chapterTitle("Chapter 1: Introduction"),
    H2("1.1 Introduction"),
    P("Eating out is a central part of social life in Saudi Arabia. Families, friends and colleagues gather in restaurants and cafés, and food delivery applications have made restaurant meals part of everyday routine. Before choosing where to eat, many customers now read what others have written online, and after their visit many of them leave a review of their own. Google Maps, delivery applications and social media have therefore become a large and continuously growing record of what customers think about the food, prices, service and atmosphere of restaurants across the Kingdom."),
    P("For a restaurant owner this record is extremely valuable: it shows which dishes customers love, which complaints keep recurring, and whether service is improving or getting worse. For a researcher it is a window onto consumer behaviour and food preferences. Yet the same record is very difficult to use. A popular restaurant can collect hundreds of reviews a month; most of them are short, informal and written in Saudi or Gulf dialect rather than Modern Standard Arabic; spelling varies from writer to writer; and a single review often praises one thing and criticises another in the same sentence, as in «الكبسة لذيذة مرة بس الخدمة بطيئة» (the kabsa is very tasty, but the service is slow)."),
    P("Sentiment analysis, a branch of natural language processing (NLP), studies how to identify automatically the opinions expressed in text. Its most useful form for businesses is aspect-based sentiment analysis (ABSA), which does not stop at labelling a whole review as positive or negative but determines the sentiment expressed towards each aspect mentioned, such as food quality, price or service. Most mature ABSA tools, however, were built for English. Arabic, and Saudi dialect in particular, poses additional challenges: rich morphology, attached prefixes and suffixes, inconsistent spelling, dialect-specific vocabulary, and negation patterns such as «مو» and «ما» that general tools often miss."),
    P("This project responds to that gap by building and evaluating an AI platform that analyses Arabic restaurant reviews, measures overall sentiment, identifies the sentiment towards seven restaurant aspects, extracts the dishes customers mention, and turns the results into dashboards and reports that a non-technical restaurant owner or researcher can use directly."),

    H2("1.2 Problem Statement"),
    P("Saudi restaurants and researchers who study them face four related problems:"),
    numbers([
      "**Volume.** The number of online reviews is too large to read manually, so most of the feedback customers provide is never used.",
      "**Language.** Reviews are written mostly in Saudi and Gulf dialect, with informal spelling, elongated letters (for example «حلووو») and emojis. General-purpose sentiment tools trained on English or on Modern Standard Arabic handle this language poorly.",
      "**Granularity.** A single overall score hides what matters. A review can be positive about the food and negative about the price at the same time; an owner needs to know which aspect drives satisfaction and which drives complaints.",
      "**Trust.** Many AI tools behave as black boxes and present uncertain results as certain. Business decisions and academic conclusions require results that can be explained, that show their uncertainty, and that are evaluated against real annotated data.",
    ]),
    P("There is therefore a need for an accessible, Arabic-first system that analyses restaurant reviews at the aspect level, handles Saudi dialect, explains its decisions, reports its uncertainty honestly, and is evaluated rigorously on real Saudi data."),

    H2("1.3 Objectives"),
    P("The main objective of this project is to design, implement and evaluate an AI platform for analysing customer sentiment and food-preference indicators in Saudi restaurant reviews. The specific objectives are:"),
    numbers([
      "To build an Arabic text-processing module that cleans and normalises reviews while preserving negation words, emojis and other signals that carry sentiment.",
      "To develop an aspect-based sentiment analyser for Modern Standard Arabic and Saudi dialect that classifies the overall sentiment of a review as positive, negative or neutral, detects mixed and uncertain cases, and assigns a sentiment to each of seven aspects: food quality and taste, price and value, quantity and portion size, service, delivery, cleanliness, and ambiance.",
      "To extract dish names from reviews using an editable dictionary of Saudi and international dishes, linking each dish to the sentiment expressed about it without inventing dishes that are not mentioned.",
      "To build a machine-learning baseline with scikit-learn and compare it with the lexicon-based analyser.",
      "To store reviews and results in a relational SQLite database with proper keys and integrity constraints.",
      "To provide an interactive Arabic right-to-left web interface for importing data, running analyses, comparing restaurants and exporting Excel and PDF reports.",
      "To evaluate the system on a real, publicly available dataset of annotated Saudi restaurant reviews using a held-out test set.",
    ]),
    P("The evaluation is guided by three research questions:"),
    ...table("Research questions and how each one is answered", ["Research question", "How it is answered"], [
      ["**RQ1.** How accurately can a lexicon- and rule-based analyser classify the sentiment of Saudi restaurant reviews, overall and per aspect?", "Comparison with the AQTE annotations on the held-out test split: overall sentiment, aspect detection and aspect sentiment."],
      ["**RQ2.** Does a supervised machine-learning model (scikit-learn) outperform the lexicon-based analyser for overall sentiment?", "Both models evaluated on the same test split with the same metrics."],
      ["**RQ3.** Which aspects and dishes are most associated with customer satisfaction and complaints?", "Analysis of the full dataset with the platform: aspect frequencies, sentiment by aspect and by dish."],
    ], [0.55, 0.45]),

    H2("1.4 Significance of the Study"),
    P("The project is significant for several groups:"),
    bullets([
      "**Restaurant owners and managers** obtain a practical tool that turns hundreds of informal reviews into a clear picture of strengths and complaints, broken down by aspect and by dish, together with recommendations and exportable reports.",
      "**Researchers in consumer behaviour and food studies** obtain a reproducible way to measure preference indicators from text, with explicit warnings about what the data can and cannot show (for example, that frequent mention of a dish is not evidence of high sales).",
      "**Arabic NLP** benefits from a documented, dialect-aware lexicon and rule set for the restaurant domain, together with an evaluation that reports both strengths and weaknesses on real data.",
      "**Students and practitioners** can study an end-to-end, tested and open implementation that runs locally without paid services, which makes it suitable for teaching and for small businesses with limited budgets.",
    ]),

    H2("1.5 Scope of the Project"),
    P("To keep the project achievable and its results meaningful, its scope was defined as follows:"),
    ...table("Project scope", ["In scope", "Out of scope"], [
      ["Arabic restaurant reviews in Modern Standard Arabic and Saudi/Gulf dialect, with some common English words", "Other languages and other business domains"],
      ["Overall sentiment (positive, negative, neutral) with confidence, mixed and uncertain flags", "Fine-grained emotions such as anger or joy"],
      ["Seven restaurant aspects and dish extraction from a dictionary of 57 dishes", "Automatic discovery of new aspect categories or new dishes"],
      ["Importing CSV, Excel, JSON and Parquet files, and official APIs that the user is authorised to use", "Web scraping or any collection that bypasses platform terms of service"],
      ["Local deployment on a personal computer with SQLite", "Cloud deployment, user accounts and multi-tenant access"],
      ["Evaluation on the public AQTE dataset of Saudi restaurant reviews", "Collection and manual annotation of a new large dataset"],
      ["A scikit-learn baseline; optional support for pre-trained Transformer models", "Fine-tuning of large language models, which requires GPU resources"],
    ], [0.5, 0.5]),

    H2("1.6 Report Structure"),
    P("The rest of this report is organised as follows. **Chapter 2** reviews the literature on sentiment analysis, aspect-based sentiment analysis and Arabic sentiment analysis, and identifies the gap this project addresses. **Chapter 3** describes the methodology: the development approach, the dataset and its annotations, text preprocessing, the lexicon-based analyser, dish extraction, the machine-learning baseline, the iterative development of the lexicon and the evaluation design. **Chapter 4** presents the system analysis, feasibility study, design and implementation of the platform. **Chapter 5** reports and discusses the results and evaluates the project against its objectives. **Chapter 6** concludes the report and proposes future work. The references and appendices follow."),
  ];
};
