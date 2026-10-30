module.exports = (K, X) => {
  const { P, H2, table, code, bullets } = K;
  const ref = (t) => new X.Paragraph({ children: K.runs(t), indent: { left: 720, hanging: 720 }, spacing: { after: 120 }, alignment: X.AlignmentType.LEFT });
  const refs = [
    "Abdelgwad, M. M., Soliman, T. H. A., Taloba, A. I., & Farghaly, M. F. (2022). Arabic aspect based sentiment analysis using bidirectional GRU based models. *Journal of King Saud University – Computer and Information Sciences, 34*, 6652–6662. https://doi.org/10.1016/j.jksuci.2021.08.030",
    "Abdul-Mageed, M., Elmadany, A., & Nagoudi, E. M. B. (2021). ARBERT & MARBERT: Deep bidirectional transformers for Arabic. In *Proceedings of the 59th Annual Meeting of the Association for Computational Linguistics and the 11th International Joint Conference on Natural Language Processing (ACL-IJCNLP 2021)* (pp. 7088–7105). Association for Computational Linguistics. https://doi.org/10.18653/v1/2021.acl-long.551",
    "Abu Farha, I., Zaghouani, W., & Magdy, W. (2021). Overview of the WANLP 2021 shared task on sarcasm and sentiment detection in Arabic. In *Proceedings of the Sixth Arabic Natural Language Processing Workshop* (pp. 296–305). Association for Computational Linguistics.",
    "Al-Dabet, S., Tedmori, S., & Al-Smadi, M. (2021). Enhancing Arabic aspect-based sentiment analysis using deep learning models. *Computer Speech & Language, 69*.",
    "Alharbi, L. M., & Qamar, A. M. (2022). Arabic sentiment analysis of eateries' reviews using deep learning. *Ingénierie des Systèmes d'Information, 27*(3), 503–508.",
    "AlMasaud, A., & Al-Baity, H. H. (2023). AraMAMS: Arabic multi-aspect, multi-sentiment restaurants reviews corpus for aspect-based sentiment analysis. *Sustainability, 15*(16), 12268. https://doi.org/10.3390/su151612268",
    "Almuqren, L., & Cristea, A. (2021). AraCust: A Saudi telecom tweets corpus for sentiment analysis. *PeerJ Computer Science, 7*, e510. https://doi.org/10.7717/peerj-cs.510",
    "Al-Thubaity, A., Alkhereyf, S., Murayshid, H., Alshalawi, N., Omirah, M., Alateeq, R., Almutairi, R., Alsuwailem, R., Alhassoun, M., & Alkhanen, I. (2023). Evaluating ChatGPT and Bard AI on Arabic sentiment analysis. In *Proceedings of ArabicNLP 2023* (pp. 335–349). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.arabicnlp-1.27",
    "bayandashnan. (2026). *AQTE: Arabic Quote & Triplet Extraction dataset* [Data set]. Hugging Face. https://huggingface.co/datasets/bayandashnan/AQTE-Arabic-Quote-Triplet-Extraction [[replace with the citation given on the dataset page, if any]]",
    "Bensoltane, R., & Zaki, T. (2022). Aspect-based sentiment analysis: An overview in the use of Arabic language. *Artificial Intelligence Review*, [[volume(issue), pages]]. https://doi.org/10.1007/s10462-022-10215-3",
    "Inoue, G., Alhafni, B., Baimukan, N., Bouamor, H., & Habash, N. (2021). The interplay of variant, size, and task type in Arabic pre-trained language models. In *Proceedings of the Sixth Arabic Natural Language Processing Workshop* (pp. 92–104). Association for Computational Linguistics.",
    "Jurafsky, D., & Martin, J. H. (2026). *Speech and language processing* (3rd ed. draft). Stanford University. https://web.stanford.edu/~jurafsky/slp3/",
    "Khondaker, M. T. I., Waheed, A., Nagoudi, E. M. B., & Abdul-Mageed, M. (2023). GPTAraEval: A comprehensive evaluation of ChatGPT on Arabic NLP. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 220–247). Association for Computational Linguistics.",
    "scikit-learn developers. (2026). *scikit-learn: Machine learning in Python* [Documentation]. https://scikit-learn.org/stable/",
    "Shi, Z., & Agrawal, R. (2025). A comprehensive survey of contemporary Arabic sentiment analysis: Methods, challenges, and future directions. In *Findings of the Association for Computational Linguistics: NAACL 2025* (pp. 3760–3772). Association for Computational Linguistics.",
    "Streamlit Inc. (2026). *Streamlit documentation*. https://docs.streamlit.io/",
    "Zhang, W., Li, X., Deng, Y., Bing, L., & Lam, W. (2023). A survey on aspect-based sentiment analysis: Tasks, methods, and challenges. *IEEE Transactions on Knowledge and Data Engineering, 35*(11), 11019–11038. https://doi.org/10.1109/TKDE.2022.3230975",
  ];
  return [
    X.chapterTitle("References"),
    ...refs.map(ref),

    X.chapterTitle("Appendices"),
    H2("Appendix A: Installation and User Guide"),
    P("**Requirements:** Python 3.10 or later and Git (optional). The steps below are for Windows; on macOS or Linux use `python3` and `source .venv/bin/activate`."),
    P("**1. Download the project** from the GitHub repository (branch `claude/practical-shannon-77t9ub`), either as a ZIP file or with:"),
    ...code(["git clone -b claude/practical-shannon-77t9ub https://github.com/Amer-omran/biobank.git"]),
    P("**2. Create and activate a virtual environment, and install the libraries** (once):"),
    ...code(["cd biobank\\saudi_restaurant_analytics", "python -m venv .venv", ".venv\\Scripts\\activate", "pip install -r requirements.txt"]),
    P("**3. Start the platform** (each time):"),
    ...code(["cd biobank\\saudi_restaurant_analytics", ".venv\\Scripts\\activate", "streamlit run app.py"]),
    P("**4. Use it:** the browser opens at http://localhost:8501. To try it quickly, press «تحميل البيانات التجريبية وتحليلها» on the home page. To analyse real data, import a file on the «استيراد البيانات» page, choose the columns, run the analysis on the «تحليل المشاعر» page, and explore the other pages."),
    P("**5. Reproduce the evaluation** (after downloading `train_split.json` and `test_split.json` from the AQTE page into the project folder):"),
    ...code(["python scripts/evaluate_aqte.py test_split.json --train train_split.json", "python scripts/error_analysis_aqte.py train_split.json --limit 2000", "python scripts/prepare_aqte.py train_split.json"]),
    P("**6. Run the automated tests:**"),
    ...code(["python -m pytest"]),

    H2("Appendix B: Lexicon Change Log"),
    ...table("Lexicon changes by version", ["Version", "Changes", "Reason"], [
      ["1.1", "Added جيد، كويس، اخلاق، احترام، ترحيب، اشكر، بطل، تجنن، فاخر; the phrases «لا بأس» and «زي العسل»; raised «معقول» to 0.8; made speed words conditional (delivery if mentioned, otherwise service); new aspect keywords طعام، قهوة، مشروبات، حلويات، معمار، تصميم", "Most frequent words in missed quotes on the training sample"],
      ["1.2", "Restored «عادي» (−0.3) and «زحمة» (−0.7)", "Their removal relied on misread labels and lowered macro-F1 against star ratings (0.603 → 0.584)"],
      ["1.3", "Single-word phrases now matched (لاباس، ماشاءالله، ماقصروا، لايفوتكم); ta marbuta restored before suffixes (خدمتهم → خدمة)", "Two software defects revealed by the second error analysis"],
      ["1.3", "Quantity: راهية، يكفي، تكفي، كافي، موزونة، بخيل. Price: متناول، أغلى; aspect words شارج، مينيموم، ضريبة. Service: لطيف; waiting phrases; إدارة، صاحب المحل. Delivery: تغليف، سفري، أكياس، تطبيقات، يوصل. Cleanliness: نضيف، وصخ، ذبان، شعر، مكشوف، رائحة. Ambiance: هدوء، أجمل، مزدحم، قديم (place only). Neutral: متوسط. Rule: «يحتاج + aspect» treated as absence. Dishes: شوربة، بيض", "Second error analysis (210 suggested terms)"],
      ["1.3 (rejected)", "Function words (عندهم، جربت، ولا، فقط، كله، يوجد، صراحه، يعتبر، عشان، ايش); names (ابو، حسن); ambiguous words (الطلب، ساعة alone، زيت، داخلية، خارجية); numeric prices", "Not opinion or aspect words, or ambiguous between aspects"],
    ], [0.12, 0.6, 0.28]),

    H2("Appendix C: Example Analyser Outputs"),
    P("The following outputs were produced by the final analyser (version 1.3):"),
    ...table("Example outputs of the analyser", ["Review", "Overall", "Aspects"], [
      ["الأكل لذيذ والخدمة سيئة", "Neutral (mixed, uncertain)", "Food quality: positive; Service: negative"],
      ["ما عجبني الأكل بس الخدمة ممتازة", "Positive (mixed)", "Food quality: negative; Service: positive"],
      ["الكبسة غالية مرة", "Negative", "Price: negative (linked to kabsa)"],
      ["المكان مافي نظافة", "Negative", "Cleanliness: negative"],
      ["الأكل والخدمة ممتازين", "Positive", "Food quality: positive; Service: positive"],
      ["الاسعار متوسطة", "Neutral", "Price: neutral"],
      ["الكمية ما تكفي", "Negative", "Quantity: negative"],
      ["خدمتهم ممتازة", "Positive", "Service: positive"],
      ["طلبت شاورما", "Neutral (uncertain: no opinion)", "Dish: shawarma, no opinion"],
    ], [0.38, 0.27, 0.35]),

    H2("Appendix D: Source Code Repository"),
    P("The complete source code, tests, dish dictionary, lexicon change log and evaluation scripts are available in the project repository: https://github.com/Amer-omran/biobank (branch `claude/practical-shannon-77t9ub`, folder `saudi_restaurant_analytics`)."),
  ];
};
