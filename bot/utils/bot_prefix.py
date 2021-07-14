import firebase_admin
from firebase_admin import firestore

from bot.constants import Client

class BotPrefixHandler():
    """
    handles bot prefixes across servers
    """
    
    #firebase_admin.initialize_app(Client.firebase_creds)

    def get_prefix(self, message):
        db = firestore.client()
        prefixes_ref = db.collection("prefixes")
        docs = prefixes_ref.stream()
        prefix = ""
        
        for doc in docs:
            if doc.id == str(message.guild.id):
                prefix = doc.to_dict()["prefix"]
                
            else:
                continue

        return prefix