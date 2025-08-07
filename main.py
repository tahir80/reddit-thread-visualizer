import streamlit as st
import praw
import networkx as nx
from pyvis.network import Network
import tempfile
import re
from prawcore.exceptions import NotFound, PrawcoreException

# Initialize Reddit API
reddit = praw.Reddit(
    client_id=st.secrets["client_id"],
    client_secret=st.secrets["client_secret"],
    user_agent="datascrapper by /u/Status-Ring1334"
)

# Safer post ID extraction
def extract_post_id(url_or_id):
    if "reddit.com" in url_or_id:
        match = re.search(r"comments/([a-z0-9]+)/", url_or_id)
        if match:
            return match.group(1)
        else:
            raise ValueError("❌ Invalid Reddit URL format.")
    return url_or_id.strip()

# Build a tree recursively
def build_tree(comment, G, parent_id=None, op_username=None):
    cid = comment.id
    author = str(comment.author)
    delta = getattr(comment, 'distinguished', None) == 'delta'
    G.add_node(cid, label=comment.body[:60], author=author, delta=delta, op=(author == op_username))
    if parent_id:
        G.add_edge(parent_id, cid)
    if hasattr(comment, "replies"):
        for reply in comment.replies:
            build_tree(reply, G, cid, op_username)

# Render tree with Pyvis
def render_tree(G, filter_mode="all"):
    net = Network(height="600px", directed=True)
    for node, data in G.nodes(data=True):
        label = data["label"]
        title = f"Author: {data['author']}"
        color = "#97C2FC"
        if data["op"]:
            color = "#FB7E81"
        if data["delta"]:
            color = "#7BE141"
        if filter_mode == "op_only" and not data["op"]:
            continue
        if filter_mode == "delta_only" and not data["delta"]:
            continue
        net.add_node(node, label=label, title=title, color=color)
    for src, dst in G.edges():
        if net.get_node(src) and net.get_node(dst):
            net.add_edge(src, dst)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    net.save_graph(tmp_file.name)
    return tmp_file.name

# Generate code snippet
def generate_code(post_id, node_id):
    return f"""import praw

reddit = praw.Reddit(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    user_agent="reddit_tree_extractor"
)

submission = reddit.submission(id="{post_id}")
submission.comments.replace_more(limit=None)

def find_comment(comment, target_id):
    if comment.id == target_id:
        return comment
    for reply in getattr(comment, "replies", []):
        found = find_comment(reply, target_id)
        if found:
            return found
    return None

target = find_comment(submission, "{node_id}")
print(target.body if target else "Comment not found.")
"""

# ==== Streamlit UI ====
st.title("🌳 Reddit Thread Visualizer")

post_input = st.text_input("Enter Reddit post URL or ID:")
filter_mode = st.selectbox("Filter tree by:", ["all", "op_only", "delta_only"])

if post_input:
    try:
        post_id = extract_post_id(post_input)
        submission = reddit.submission(id=post_id)
        submission.comments.replace_more(limit=None)

        G = nx.DiGraph()
        op_username = str(submission.author)

        for top_level in submission.comments:
            build_tree(top_level, G, None, op_username)

        html_path = render_tree(G, filter_mode)
        st.components.v1.html(open(html_path, 'r', encoding='utf-8').read(), height=650, scrolling=True)

        selected_comment = st.text_input("Enter a comment ID to generate code snippet:")
        if selected_comment:
            st.code(generate_code(post_id, selected_comment), language='python')

    except ValueError as ve:
        st.error(str(ve))
    except NotFound:
        st.error("❌ Reddit post not found. Please check the ID or URL. It might be private or deleted.")
    except PrawcoreException as pe:
        st.error(f"❌ Reddit API error: {str(pe)}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
