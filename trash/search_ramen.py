# search_ramen.py

from ramen_qa import answer_ramen

def main():
    print("❓ 質問をどうぞ（終了は Ctrl+C）")
    while True:
        q = input("> ").strip()
        if not q:
            continue
        print("\n🤖", answer_ramen(q), "\n")

if __name__ == "__main__":
    main()



