from ..Databases.mongo import Bot_Retrieval

def on_boarding_Data(chatbot_id, version_id):
    Bot_information = Bot_Retrieval(chatbot_id, version_id)
    print(Bot_information)