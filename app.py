import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- 1. CONFIGURATION ---
# ZAROORI: Apni Google Sheet ka URL yahan st.secrets mein set karein.
# (Dekhiye niche 'Zaroori Nirdesh' section)
# Agar aap secrets use nahi kar rahe, to niche wali line mein apna URL daalein.
SPREADSHEET_URL = st.secrets.get("CHAT_DATA_URL", "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit?usp=sharing")

# Chat data aur Users data ke liye Sheet ke naam aur Column names
CHAT_WORKSHEET = "ChatData"
USERS_WORKSHEET = "Users"
CHAT_COLUMN_NAMES = ["timestamp", "sender_num", "receiver_num", "sender_name", "message_text"]
USERS_COLUMN_NAMES = ["User Name", "Phone Number"]

# --- Page Config ---
st.set_page_config(page_title="Apna Chat App", page_icon="💬", layout="wide")

# --- Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'my_number' not in st.session_state:
    st.session_state.my_number = ""
if 'my_name' not in st.session_state:
    st.session_state.my_name = ""

# --- Helper Functions ---
@st.cache_data(ttl=2) # Har 2 second mein data refresh
def load_data(conn, worksheet_name, column_names):
    """Google Sheet se data load karta hai."""
    try:
        data = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, usecols=column_names, ttl=2)
        return data.dropna(how="all")
    except Exception as e:
        st.error(f"Data load karte samay error aayi: {e}")
        return pd.DataFrame(columns=column_names)

def save_message(conn, sender_num, receiver_num, sender_name, message_text):
    """Naye message ko Google Sheet mein save karta hai."""
    new_data = pd.DataFrame([
        {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sender_num": sender_num,
            "receiver_num": receiver_num,
            "sender_name": sender_name,
            "message_text": message_text
        }
    ])
    conn.append(spreadsheet=SPREADSHEET_URL, worksheet=CHAT_WORKSHEET, data=new_data)
    # Cache ko hata do tak ki chat box turant update ho
    load_data.clear()

def register_user(conn, name, number):
    """Naye user ko Users sheet mein jodta hai (agar pehle se nahi hai)."""
    users_df = load_data(conn, USERS_WORKSHEET, USERS_COLUMN_NAMES)
    
    # Agar user ka number pehle se hai to register nahi karna
    if number not in users_df['Phone Number'].values:
        new_user = pd.DataFrame([
            {
                "User Name": name,
                "Phone Number": number
            }
        ])
        conn.append(spreadsheet=SPREADSHEET_URL, worksheet=USERS_WORKSHEET, data=new_user)
        load_data.clear() # Users cache clear karo

# --- 1. LOGIN SCREEN ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Google Sheets Connection Error. Please check your setup.")
    st.stop()
    
if not st.session_state.logged_in:
    st.title("🔐 Login Karein")
    st.write("Chat shuru karne ke liye apni details dalein.")
    
    with st.form("login_form"):
        name_input = st.text_input("Apna Naam (Display Name)")
        number_input = st.text_input("Apna Phone Number (10 Ang)", max_chars=10)
        submitted = st.form_submit_button("Login")
        
        if submitted:
            # Check: Number sirf digits ho aur 10 ho
            if name_input and number_input.isdigit() and len(number_input.strip()) == 10:
                st.session_state.my_name = name_input
                st.session_state.my_number = number_input.strip()
                st.session_state.logged_in = True
                
                # User ko Users sheet mein register karo
                register_user(conn, st.session_state.my_name, st.session_state.my_number)
                st.rerun() 
            else:
                st.error("कृपया सही 10 अंकों का नंबर और अपना नाम दोनों भरें।")
    
    st.stop()

# --- 2. MAIN CHAT SCREEN (Login ke baad) ---

# Sidebar mein user ki info
st.sidebar.header(f"👤 {st.session_state.my_name}")
st.sidebar.caption(f"My Number: {st.session_state.my_number}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.title("💬 Real-time Chat")

# --- Name Selection (Aapki Zaroorat ke mutabik) ---

# 1. Users list load karo
users_df = load_data(conn, USERS_WORKSHEET, USERS_COLUMN_NAMES)
available_friends = users_df[users_df['Phone Number'] != st.session_state.my_number]
friend_names_list = available_friends['User Name'].tolist()

if not friend_names_list:
    st.warning("कोई दोस्त नहीं मिला। कृपया Google Sheet में 'Users' लिस्ट चेक करें।")
    st.stop()

# Dropdown se naam chunein
selected_friend_name = st.selectbox(
    "💬 जिस दोस्त से बात करनी है, उसका नाम चुनें:",
    options=['--- दोस्त चुनें ---'] + friend_names_list
)

if selected_friend_name == '--- दोस्त चुनें ---':
    st.info("चैट शुरू करने के लिए सूची से एक दोस्त का नाम चुनें।")
    st.stop()

# Name ke aadhar par uska number dhundo
friend_number = available_friends[available_friends['User Name'] == selected_friend_name]['Phone Number'].iloc[0]

# --- 3. CHAT DISPLAY ---
st.subheader(f"Chatting with: {selected_friend_name}")
chat_container = st.container(height=400, border=True)

# 2. Data Load karo
all_messages = load_data(conn, CHAT_WORKSHEET, CHAT_COLUMN_NAMES)

# 3. Messages ko filter karo (Sirf current conversation ke liye)
my_num = st.session_state.my_number
chat_filter = (
    ((all_messages['sender_num'] == my_num) & (all_messages['receiver_num'] == friend_number)) |
    ((all_messages['sender_num'] == friend_number) & (all_messages['receiver_num'] == my_num))
)

current_chat = all_messages[chat_filter].sort_values(by="timestamp", ascending=True)

# 4. Chat Display karo
with chat_container:
    if current_chat.empty:
        st.info(f"अभी तक {selected_friend_name} के साथ कोई मैसेज नहीं है। पहला मैसेज भेजें!")
    else:
        for index, row in current_chat.iterrows():
            # Agar message maine bheja hai
            if row['sender_num'] == my_num:
                st.chat_message("user").write(row['message_text'])
            # Agar message usne bheja hai
            else:
                st.chat_message("assistant", avatar="🧑‍💻").write(f"**{row['sender_name']}:** {row['message_text']}")


# --- 4. MESSAGE INPUT BOX ---
message_input = st.chat_input(f"{selected_friend_name} ko message likhein...")

if message_input:
    # Message save karo
    save_message(conn, st.session_state.my_number, friend_number, 
                 st.session_state.my_name, message_input)
    # Page ko refresh karo taaki naya message dikhe
    st.rerun()

# 5. Har 2 second mein chat refresh ho
time.sleep(2)
st.rerun()
