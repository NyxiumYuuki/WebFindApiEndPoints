import os
import argparse
import asyncio
import csv
import json
import logging
import sys
from typing import Dict, Any, List, Tuple
from collections import Counter
import tqdm
from aiohttp import ClientSession


# python web_find_api_end_points.py
#   --url https://gameinfo.albiononline.com/api/gameinfo/guilds/
#   --dict dict.txt
#   --output {url}-tested.csv

# output.csv
#   base_url;word_tested;url;status_code;response_json;response_content


def main():
    args = set_argparse()
    asyncio.get_event_loop().run_until_complete(
        web_find_api_end_points(
            args.url,
            args.wordlist,
            args.prefix,
            args.output
        )
    )

    exit(0)


def set_argparse():
    parser = argparse.ArgumentParser(description='')
    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    required.add_argument('-u', '--url', help=f'(default: None)', default=None, required=True)
    required.add_argument('-w', '--wordlist', help=f'Word list to brute force (default: None)', default=None,
                          required=True)

    optional.add_argument('-p', '--prefix', help=f'Prefix (default: None)', default=None)
    optional.add_argument('-o', '--output', help=f'Output file (default: <url>_<wordlist>_results.csv)', default=None)

    optional.add_argument('-i', '--info', help='Info mode (default: True)', default=True, action='store_false')
    optional.add_argument('-d', '--debug', help='Debug mode (default: False)', default=False, action='store_true')

    try:
        args = parser.parse_args()
    except argparse.ArgumentError as error:
        logging.error('Catching an argumentError {}'.format(error))
        sys.exit('Catching an argumentError {}'.format(error))

    if args.debug:
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    elif args.info:
        logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    else:
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

    return args


async def web_find_api_end_points(url, word_list_file, prefix, output_file):
    if prefix is not None:
        url = f'{url}{prefix}'

    if output_file is None:
        output_file = f'outputs/{url.replace("/", "_").replace(":", "")}_{os.path.basename(word_list_file).split(".")[0]}_results.csv'

    txtFile = open(word_list_file, 'r')
    words = txtFile.read().splitlines()
    txtFile.close()

    outputFile = open(output_file, 'w', newline='')
    csvFile = csv.writer(outputFile, delimiter=';')
    csvFile.writerow(['base_url', 'word_tested', 'url', 'status_code', 'response_json', 'response_content'])

    logging.info(f'Example url tested : {url}{words[0]}')

    session = ClientSession()
    results = await http_get_with_aiohttp_parallel(session, url, words)
    await session.close()
    csvFile.writerows(results)

    status_codes = [result[3] for result in results]
    dict_status = json.dumps(dict(Counter(status_codes)), indent=4)
    outputFile.close()
    logging.info(dict_status)
    return dict_status


async def http_get_with_aiohttp_parallel(session: ClientSession, base_url: str, words: List[str], headers: Dict = {}, proxy: str = None, timeout: int = 10) -> (List[Tuple[int, Dict[str, Any], bytes]], float):
    tasks = []
    for word in words:
        task = asyncio.create_task(http_get_with_aiohttp(session, base_url, word, f'{base_url}{word}', headers, proxy, timeout))
        tasks.append(task)

    results = [
        await f
        for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))
    ]
    return results


class Wrapper:

    def __init__(self, session):
        self._session = session

    async def get(self, url, headers, proxy, timeout):
        try:
            return await self._session.get(url, headers=headers, proxy=proxy, timeout=timeout)
        except Exception as e:
            logging.error(e)
            return None


async def http_get_with_aiohttp(session: ClientSession, base_url: str, word: str, url: str, headers: Dict = {}, proxy: str = None, timeout: int = 30) -> (int, Dict[str, Any], bytes):
    wrapper = Wrapper(session)
    response = await wrapper.get(url=url, headers=headers, proxy=proxy, timeout=timeout)

    if response is not None:
        response_json = None
        try:
            response_json = await response.json(content_type=None)
        except json.decoder.JSONDecodeError as e:
            pass

        response_content = None
        try:
            response_content = await response.read()
        except:
            pass
        return base_url, word, url, response.status, response_json, response_content
    else:
        return base_url, word, url, None, None, None


if __name__ == '__main__':
    main()
