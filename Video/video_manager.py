import random

class VideoManager:
    def __init__(self):
        self.pool = {}
        self.original_order = [] # 记录上传时的原始顺序

    def add_videos(self, video_paths):
        for path in video_paths:
            if path not in self.pool:
                self.pool[path] = 0
                self.original_order.append(path)

    def clear(self):
        self.pool.clear()
        self.original_order.clear()

    def get_videos_for_merge(self, count, mode="随机合并"):
        if not self.pool:
            return []

        selected = []
        for _ in range(count):
            # 找到当前使用次数最少的频次
            min_usage = min(self.pool.values())
            
            # 按照原始顺序提取所有符合最小使用次数的候选视频
            candidates = [k for k in self.original_order if self.pool[k] == min_usage]
            
            if not candidates:
                break
                
            if mode == "随机合并":
                chosen = random.choice(candidates)
            else:
                # 按顺序合并：永远选取候选项中的第一个
                chosen = candidates[0]
                
            selected.append(chosen)
            self.pool[chosen] += 1
            
        return selected