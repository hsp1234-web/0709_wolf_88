import abc

class BaseQueue(abc.ABC):
    """
    任務佇列抽象基底類別。
    定義了所有佇列實現都必須提供的標準介面。
    """

    @abc.abstractmethod
    def put(self, task_data: dict) -> None:
        """
        將一個新任務放入佇列。

        Args:
            task_data (dict): 要執行的任務內容，必須是可序列化為 JSON 的字典。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get(self) -> dict | None:
        """
        從佇列中取出一個待處理的任務。
        此操作應具備原子性，防止多個工作者取得同一個任務。

        Returns:
            dict | None: 如果佇列中有任務，則返回任務內容；否則返回 None。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def task_done(self, task_id: any) -> None:
        """
        標記一個任務已完成。

        Args:
            task_id (any): 已完成任務的唯一識別碼。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def qsize(self) -> int:
        """
        返回佇列中待處理任務的數量。

        Returns:
            int: 待處理任務的數量。
        """
        raise NotImplementedError
