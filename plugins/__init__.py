class PluginManager:
    def __init__(self):
        self.plugins = {}
    
    def load_all(self):
        from plugins import education, shop, task, admin, system
        self.plugins["education"] = education.EducationPlugin()
        self.plugins["shop"] = shop.ShopPlugin()
        self.plugins["task"] = task.TaskPlugin()
        print(f"✅ נטענו {len(self.plugins)} פלאגאינים")
    
    def get(self, name):
        return self.plugins.get(name)

pm = PluginManager()
