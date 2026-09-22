from src.llm.schema_context import build_schema_context


questions = [
    "What are the top 5 product categories by revenue?",
    "How many units did we sell?",
    "What was revenue by country?",
    "Which stores sold the most products?",
]


for question in questions:

    print("=" * 80)
    print(f"QUESTION: {question}")
    print("=" * 80)

    context = build_schema_context(question)

    print(context)
    print()