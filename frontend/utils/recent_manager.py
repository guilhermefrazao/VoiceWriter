import json
import os

class RecentManager:
    def __init__(self, filename="recent_folders.json", max_items=10):
        self.filename = filename
        self.max_items = max_items
        self.recent_paths = self._load_from_disk()

   
    def _load_from_disk(self):
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

   
    def save_to_disk(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.recent_paths, f, ensure_ascii=False, indent=4)

   
    def add_path(self, path: str):
        path = os.path.normpath(path)

        if path in self.recent_paths:
            self.recent_paths.remove(path)
        
        self.recent_paths.insert(0, path)
        
        if len(self.recent_paths) > self.max_items:
            self.recent_paths = self.recent_paths[:self.max_items]
            
        self.save_to_disk()

    
    def get_recents(self):
        valid_paths = [p for p in self.recent_paths if os.path.exists(p)]
        
        if len(valid_paths) != len(self.recent_paths):
            self.recent_paths = valid_paths
            self.save_to_disk()
            
        return valid_paths

   
    def clear_recents(self):
        self.recent_paths = []
        self.save_to_disk()