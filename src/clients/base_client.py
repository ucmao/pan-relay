from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Union


class BasePanClient(ABC):
    """
    网盘客户端统一抽象基类。
    所有网盘客户端（百度、夸克、阿里、UC、迅雷等）均需实现该接口。
    """

    @abstractmethod
    def store(
        self, share_url: str, to_pdir_path: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        转存指定的网盘分享链接，并在个人网盘中生成新分享链接。

        :param share_url: 他人分享的网盘 URL
        :param to_pdir_path: 转存的目标网盘目录路径，默认为根目录 '/'
        :return: (file_id, file_name, new_share_url) 三元组，转存失败时相应项为 None
        """
        pass

    @abstractmethod
    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        """
        从个人网盘中删除指定的文件或目录。

        :param file_ids: 单个文件 ID/路径，或文件 ID/路径列表
        :return: 删除成功返回 True，失败返回 False
        """
        pass

    def delete_file(self, file_ids: Union[str, List[str]]) -> bool:
        """del_file 的规范命名别名"""
        return self.del_file(file_ids)

    def transfer_and_share(
        self, share_url: str, to_pdir_path: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """store 的规范命名别名"""
        return self.store(share_url, to_pdir_path=to_pdir_path)

    def get_or_create_dir(self, dir_name: str, parent_id: str = "0") -> str:
        """
        获取指定名称的文件夹 ID 或路径，若不存在则自动新建。
        各网盘客户端可重写此方法。默认返回传入的 parent_id。
        """
        return parent_id

    def add_ad(self, dir_id_or_path: str, ad_share_url: Optional[str] = None) -> bool:
        """
        向指定的转存目标目录/文件夹植入个人自定义引流文件。
        各网盘客户端可重写此方法。默认未实现返回 False。
        """
        return False

