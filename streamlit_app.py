import streamlit as st
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma

# Load environment variables
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Load book data
books = pd.read_csv("books_with_emotions.csv")
books["large_thumbnail"] = books["thumbnail"] + "&fife=w880"
books["large_thumbnail"] = np.where(
    books["large_thumbnail"].isna(),
    "cover_not_found.jpg",
    books["large_thumbnail"],
)

# Load and process descriptions
raw_documents = TextLoader("tagged_description.txt", encoding="utf-8").load()
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100, separator="\n")
documents = text_splitter.split_documents(raw_documents)
db_books = Chroma.from_documents(documents, OpenAIEmbeddings())

# Sidebar filters
st.sidebar.title("🔍 Filter Options")
query = st.sidebar.text_input("Describe a book you like", placeholder="e.g., A journey of resilience and hope")
category = st.sidebar.selectbox("Select Category", ["All"] + sorted(books["simple_categories"].unique()))
tone = st.sidebar.selectbox("Select Emotional Tone", ["All", "Happy", "Surprising", "Angry", "Suspenseful", "Sad"])
submit = st.sidebar.button("Find Recommendations")

def retrieve_semantic_recommendations(query, category=None, tone=None, initial_top_k=50, final_top_k=16):
    recs = db_books.similarity_search(query, k=initial_top_k)
    books_list = []
    for rec in recs:
        try:
            first_token = rec.page_content.strip('"').split()[0].rstrip(":")
            book_id = int(first_token)
            books_list.append(book_id)
        except (IndexError, ValueError):
            continue

    book_recs = books[books["isbn13"].isin(books_list)]

    if category != "All" and category is not None:
        book_recs = book_recs[book_recs["simple_categories"] == category]

    book_recs = book_recs.head(final_top_k)

    if tone == "Happy":
        book_recs = book_recs.sort_values(by="joy", ascending=False)
    elif tone == "Surprising":
        book_recs = book_recs.sort_values(by="surprise", ascending=False)
    elif tone == "Angry":
        book_recs = book_recs.sort_values(by="anger", ascending=False)
    elif tone == "Suspenseful":
        book_recs = book_recs.sort_values(by="fear", ascending=False)
    elif tone == "Sad":
        book_recs = book_recs.sort_values(by="sadness", ascending=False)

    return book_recs

def recommend_books(query, category, tone):
    recommendations = retrieve_semantic_recommendations(query, category, tone)
    context = ""
    for _, row in recommendations.iterrows():
        title = row["title"]
        author = row["authors"].split(";")[0]
        desc = row["description"]
        context += f"Title: {title}\nAuthor: {author}\nDescription: {desc}\n\n"

    prompt = f"""You are a book expert.

Based on the following book descriptions:
{context}
The user is looking for a book like: "{query}"
Suggest 3 good matches from the list above. For each, explain briefly why its a good fit
"""
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )
    generated_summary = response.choices[0].message.content
    return recommendations, generated_summary

# Main display
st.title("📚 Semantic Book Recommender")
if submit and query:
    recs, explanation = recommend_books(query, category, tone)

    st.subheader("📖 Top Book Recommendations")
    for _, row in recs.iterrows():
        st.image(row["large_thumbnail"], width=120)
        st.markdown(f"**{row['title']}** by {row['authors'].replace(';', ', ')}")
        st.caption(" ".join(row["description"].split()[:30]) + "...")
        st.markdown("---")

    st.subheader("🧠 Why These Books?")
    st.markdown(explanation)