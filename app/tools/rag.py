from app.core.schema import SearchResponse
from openai import OpenAI
from chromadb import Collection


def rag_prompt(query: str, context: list[str]) -> str:
    context_str = "\n\n".join(context)

    prompt = f"""
    Use the following context to answer the question.
    If the context doesn't contain enough information, say "I don't have enough information to answer that."

    Context:
    {context_str}

    Question:
    {query}

    Formatting Instructions:
    - Use markdown format with clear structure
    - Use ### for main section headings
    - Use **bold text** for key terms and important concepts
    - Use bullet points with • (bullet character) for lists, not dashes
    - Keep each bullet point concise (1-2 lines max)
    - Add a blank line between sections for readability
    - End with a brief summary paragraph
    """
    return prompt


def get_relevant_chunks(
    collection: Collection,
    query: str,
    n_results: int = 3,
) -> list[str]:
    results = collection.query(query_texts=[query], n_results=n_results)

    docs = results.get("documents", [[]])
    if not docs or len(docs) == 0:
        return []

    return docs[0]


def generate_answer(
    client: OpenAI,
    prompt: str,
    model: str = "minimax/minimax-m2.5",
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that answers questions based on the provided context.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


def search_documents(
    collection: Collection,
    client: OpenAI,
    query: str,
    n_results: int = 3,
    model: str = "minimax/minimax-m2.5",
) -> SearchResponse:
    # Retrieve relevant chunks
    context = get_relevant_chunks(collection, query, n_results)

    if not context:
        return SearchResponse(
            query=query,
            answer="No relevant documents found.",
            context=[],
        )

    # Build prompt
    prompt = rag_prompt(query, context)

    # Generate answer
    answer = generate_answer(client, prompt, model)

    return SearchResponse(
        query=query,
        answer=answer or "Sorry, I don't know the answer to that question.",
        context=context,
    )
