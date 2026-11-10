# CliMa v13 — বাংলা ড্যাশবোর্ড ও এক্সপোর্ট

- বাংলা ডিফল্ট ও ভাষা বদলানোর বোতাম বাদ। ব্যবহারকারীর ইংরেজি নাম এবং অনুরোধকৃত EVERYDAY RESILIENT HEALTH ব্র্যান্ড অপরিবর্তিত।
- আইকনসহ অ্যাপ নেভিগেশন ও মেনু; পৃথক জলবায়ু/দুর্যোগ কার্ড।
- নতুন জরিপ থেকে সময়ের ধরন ও বাংলা সাল বাদ; version 2 payload। পুরোনো version 1 রেকর্ড অক্ষত।
- Open-Meteo বর্তমান, ২৪ ঘণ্টা ও ৭ দিনের পূর্বাভাস; খোলা অ্যাপে ১৫ মিনিটে আপডেট, ব্যর্থ হলে পুরোনো তথ্য চিহ্নিত।
- সার্ভারে অনুমোদিত অ্যাডমিন একক ব্যবহারকারী অথবা ফিল্টারসহ সব ব্যবহারকারীর Excel এবং CSV ZIP ডাউনলোড করতে পারবেন। বিদ্যমান PDF সুবিধা রয়েছে। জমা দেওয়া তথ্য সার্ভারে সংরক্ষিত হয়; ফাইল তৈরি হয় ডাউনলোডের সময়।
- Cases শিটে প্রতিটি জলবায়ু মাত্রার মাস/দিন এবং প্রতিটি মাসের দুর্যোগ/প্রজনন উত্তর আলাদা কলামে। মূল nested তথ্যও রাখা হয়েছে। সব সারির কলামের সমন্বয় নেওয়া হয়—পরের রিপোর্টের বাড়তি তথ্য বাদ যায় না।
- HTML ডেমোতে নমুনা ও বর্তমানে দেওয়া তথ্য CSV/XLSX-এ পাওয়া যায়; রিলোডে মুছে যায়। বাস্তব রোগীর তথ্য ব্যবহারের জন্য চালু সার্ভার প্রয়োজন।

Validation: 22 seasonal/export/access tests passed. Demo XLSX ZIP/XML and Bengali contents validated; browser dashboard, live weather, survey and export controls checked.

Limitations: no new production deployment or signed Android build. Existing technical admin values and server-error text still require a complete Bengali language audit. No claim of comprehensive device/security/clinical validation.
