import os
from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from interview import create_interview_graph  # your detailed graph from interview.py

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
CONFIG = {"configurable": {"thread_id": "67"}}

def main():
    with MongoDBSaver.from_conn_string(MONGODB_URI) as checkpointer:
        graph = create_interview_graph(checkpointer=checkpointer)
        
        print("Interview Agent initialized. Type your messages below.")
        print("Type 'exit' or 'quit' to end the session.")
        
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting. Goodbye!")
                break
            
            response_text = ""
            try:
                for event in graph.stream(
                    {"messages": [{"role": "user", "content": user_input}]},
                    CONFIG,
                    stream_mode="values"
                ):
                    if "messages" in event:
                        for msg in event["messages"]:
                            # msg is likely a HumanMessage/AIMessage with content attribute
                            content = getattr(msg, "content", str(msg))
                            print(content)
                            response_text += content
            except Exception as e:
                print(f"❌ Error in generating response: {e}")

if __name__ == "__main__":
    main()