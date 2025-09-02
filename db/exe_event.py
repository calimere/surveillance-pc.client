class ExeEvent:
    def __init__(self, eev_id, exe_id, eev_type, eev_timestamp):
        self.eev_id = eev_id
        self.exe_id = exe_id
        self.eev_type = eev_type
        self.eev_timestamp = eev_timestamp

    def __repr__(self):
        return f"<ExeEvent {self.eev_id}: exe_id={self.exe_id}, type={self.eev_type}, ts={self.eev_timestamp}>"