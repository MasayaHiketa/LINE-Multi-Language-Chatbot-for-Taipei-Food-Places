# from ramen_qa import _vectorstore
# docs = _vectorstore.similarity_search("台北駅", k=5)
# for d in docs:
#     print(d.metadata["title"], d.metadata.get("address"), d.metadata.get("stations"))
from ramen_qa import answer_ramen

#print(answer_ramen("善導寺旁邊的拉麵有什麽？\n"))
#print(answer_ramen("台大醫院旁邊好吃的拉麵有什麽？\n"))
print(answer_ramen("中山好吃的拉麵有什麽？\n"))
print(answer_ramen("台北でおいしいラーメンは？\n"))
print(answer_ramen("Which ramen is good in taipei？\n"))
#print(answer_ramen("善導寺的拉麵有什麽？\n"))