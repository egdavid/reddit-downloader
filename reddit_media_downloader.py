import asyncio
import aiohttp
import aiofiles
import os
import urllib.parse
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
from tqdm import tqdm

@dataclass
class RedditMedia:
    url: str
    filename: str

class RedditMediaDownloader:
    def __init__(self, username: str, output_dir: str = "downloads"):
        self.username = username
        self.output_dir = output_dir
        self.base_url = "https://www.reddit.com/user/{}/submitted.json"
        self.headers = {'User-agent': 'RedditMediaDownloader 1.0'}
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    async def _create_session(self):
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def _close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_posts(self, after: Optional[str] = None) -> Dict:
        url = self.base_url.format(self.username)
        if after:
            url += f"?after={after}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"Error fetching posts: {response.status}")
                    return {}
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching posts: {str(e)}")
            return {}

    def extract_media_urls(self, data: Dict) -> List[RedditMedia]:
        media_list = []
        for post in data.get('data', {}).get('children', []):
            url = post.get('data', {}).get('url')
            if url and any(ext in url for ext in ['.jpg', '.png', '.gif', '.mp4']):
                filename = os.path.basename(urllib.parse.urlparse(url).path)
                media_list.append(RedditMedia(url=url, filename=filename))
        return media_list

    async def download_media(self, media: RedditMedia):
        file_path = os.path.join(self.output_dir, self.username, media.filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            async with self.session.get(media.url) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, mode='wb') as f:
                        await f.write(await response.read())
                    self.logger.info(f"Downloaded: {media.filename}")
                else:
                    self.logger.error(f"Error downloading {media.filename}: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"Error downloading {media.filename}: {str(e)}")

    async def download_all_media(self):
        await self._create_session()
        try:
            after = None
            total_media = 0
            
            with tqdm(desc="Downloading media", unit="file") as pbar:
                while True:
                    data = await self.fetch_posts(after)
                    media_list = self.extract_media_urls(data)
                    
                    if not media_list:
                        break
                    
                    total_media += len(media_list)
                    tasks = [self.download_media(media) for media in media_list]
                    await asyncio.gather(*tasks)
                    pbar.update(len(media_list))
                    
                    after = data.get('data', {}).get('after')
                    if not after:
                        break
            
            self.logger.info(f"Download complete! {total_media} files downloaded.")
        finally:
            await self._close_session()

async def main():
    try:
        username = input("Enter the Reddit username: ")
        downloader = RedditMediaDownloader(username)
        await downloader.download_all_media()
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())