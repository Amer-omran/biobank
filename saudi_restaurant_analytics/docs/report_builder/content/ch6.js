module.exports = (K, X) => {
  const { P, H2, bullets } = K;
  return [
    X.chapterTitle("Chapter 6: Conclusion and Future Work"),
    H2("6.1 Conclusion"),
    P("This project set out to help Saudi restaurants and researchers make use of the large volume of informal Arabic reviews that customers publish online. It designed, implemented and evaluated an AI platform that analyses these reviews at the aspect level, extracts the dishes customers mention, and presents the results in an Arabic, right-to-left interface with dashboards, comparisons and reports."),
    P("The core of the platform is a transparent lexicon- and rule-based analyser built for Modern Standard Arabic and Saudi dialect. It handles negation, intensification, contrast, implicit and aspect-dependent opinions, and it reports the evidence and the uncertainty of every decision. It was developed iteratively on training data from AQTE, a public dataset of 14,783 real Saudi restaurant reviews from Google Maps, and evaluated once on a held-out test split. Over four lexicon versions, aspect-detection F1 on the development sample rose from 0.775 to 0.814. When an aspect was detected, its sentiment was right in about nine cases out of ten, and the analyser clearly outperformed a majority-class baseline for overall sentiment. " + "[[Add one sentence with the final test results and the comparison with scikit-learn.]]"),
    P("The evaluation also showed where the approach is weak: the neutral class, rarely mentioned aspects such as delivery and quantity, sarcasm, and opinions expressed without opinion words. These limitations are reported openly in the platform itself, which flags uncertain and mixed results, shows sample sizes and refuses to rank restaurants with too few reviews."),
    P("Beyond its results, the project demonstrates a development practice that matters for applied NLP: inspect the data before writing code, keep the test data untouched, analyse errors systematically, protect every fix with a test, and scrutinise the evaluation tools as carefully as the models. Following this practice uncovered two software defects and one evaluation error that would otherwise have distorted the results."),

    H2("6.2 Limitations"),
    bullets([
      "The analyser is lexicon-based, so it cannot recognise opinion words that are not in its lexicon, and it misreads sarcasm.",
      "The neutral class and the delivery and quantity aspects have low accuracy.",
      "AQTE identifies restaurants only by their Google Maps identifiers and has no dates or cities, so comparisons between named restaurants, cities and periods could be demonstrated only with other data.",
      "The mapping of the 29 AQTE categories to seven aspects is a researcher's decision that affects the aspect results.",
      "Dish mentions are preference indicators inferred from text; without sales data, they cannot measure what customers actually buy.",
      "Pre-trained Transformer models were supported but not fine-tuned or evaluated, because of time and hardware limits.",
    ]),

    H2("6.3 Future Improvements"),
    bullets([
      "**Fine-tune an Arabic Transformer model** such as CAMeLBERT or AraBERT on AQTE, both for overall sentiment and as an aspect classifier, using a GPU environment such as Google Colab, and compare it with the current results.",
      "**Hybrid analysis:** combine the lexicon analyser, which provides evidence and aspects, with a supervised model, which provides vocabulary coverage, for example by using the model when the lexicon is uncertain.",
      "**Improve the neutral class** with explicit neutral expressions, calibrated thresholds tuned on the training data, and possibly a separate \"mixed\" category in the evaluation.",
      "**Expand rare aspects** by adding delivery and quantity expressions from more data and by learning aspect keywords automatically from annotated quotes.",
      "**Sarcasm and numeric prices:** detect sarcasm using resources such as ArSarcasm-v2 (Abu Farha et al., 2021), and interpret prices written as numbers (for example «300 ريال») so that price complaints without opinion words are recognised.",
      "**Richer data:** collect reviews with restaurant names, dates and cities through official channels, with consent, to enable trend and city analysis on real data.",
      "**Deployment:** provide a hosted version with user accounts for restaurant chains, scheduled imports from official exports, automatic monthly reports, and confidence scores calibrated on annotated data.",
    ]),
  ];
};
