class EducationPlugin:
    def __init__(self, db_path="state/db.json"):
        self.db_path = db_path
    
    def list_courses(self):
        import os, json
        courses = []
        for f in os.listdir("state/courses"):
            courses.append(json.load(open(f"state/courses/{f}")))
        return courses
