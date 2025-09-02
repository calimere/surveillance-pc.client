class ExeList:
    def __init__(self, exe_id, exe_name, exe_path, exe_program_name, exe_first_seen, exe_last_seen,
                 exe_is_unknown, exe_is_watched, exe_launched, exe_is_dangerous, exe_blocked):
        self.exe_id = exe_id
        self.exe_name = exe_name
        self.exe_path = exe_path
        self.exe_program_name = exe_program_name
        self.exe_first_seen = exe_first_seen
        self.exe_last_seen = exe_last_seen
        self.exe_is_unknown = exe_is_unknown
        self.exe_is_watched = exe_is_watched
        self.exe_launched = exe_launched
        self.exe_is_dangerous = exe_is_dangerous
        self.exe_blocked = exe_blocked

    def __repr__(self):
        return f"<ExeList {self.exe_id}: {self.exe_name} ({self.exe_path})>"