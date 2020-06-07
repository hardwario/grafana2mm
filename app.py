import click
import json
import os
import pendulum
import requests
import sys
import tempfile
import toml

with open('version.txt') as f:
    version = f.read().strip()


class MattermostClientException(Exception):
    pass


class MattermostClient:

    def __init__(self, base_url, login, password):
        self._base_url = base_url
        r = requests.post(self._base_url + '/api/v4/users/login', json={'login_id': login, 'password': password})
        if r.status_code != 200:
            raise MattermostClientException('Unexpected status code: {}'.format(r.status_code))
        token = r.headers.get('Token')
        if not token:
            raise MattermostClientException('Token not found')
        self._headers = {'Authorization': 'Bearer {}'.format(token)}

    def upload_files(self, channel_id, files):
        r = requests.post(self._base_url + '/api/v4/files', headers=self._headers, data={'channel_id': channel_id}, files=files)
        if r.status_code != 201:
            raise MattermostClientException('Unexpected status code: {}'.format(r.status_code))
        file_infos = json.loads(r.text).get('file_infos', [])
        if len(file_infos) != len(files):
            raise MattermostClientException('Number of uploaded/returned files do not match')
        return [{d['name']: d['id']} for d in file_infos if 'id' in d and 'name' in d]

    def post_message(self, channel_id, message, file_ids):
        data = {'channel_id': channel_id, 'message': message, 'file_ids': file_ids}
        r = requests.post(self._base_url + '/api/v4/posts', headers=self._headers, json=data)
        if r.status_code != 201:
            raise MattermostClientException('Unexpected status code: {}'.format(r.status_code))


class GrafanaClientException(Exception):
    pass


class GrafanaClient:

    def __init__(self, url, token):
        self._url = url
        self._token = token

    def get_image(self):
        headers = {'Authorization': 'Bearer {}'.format(self._token)}
        params = {
            'orgId': self.organization,
            'panelId': self.panel,
            'from': self.since,
            'to': self.until,
            'tz': self.timezone,
            'var-label': self.labels,
            'width': self.width,
            'height': self.height
        }
        r = requests.get(self._url, headers=headers, params=params)
        if r.status_code != 200:
            raise GrafanaClientException('Unexpected status code: {}'.format(r.status_code))
        return r.content


@click.command()
@click.option('-c', '--config', required=True, type=click.Path(exists=True), help='Configuration file (TOML format).')
@click.version_option(version=version)
def main(config):
    config = toml.load(config)

    now = pendulum.now()
    until = pendulum.datetime(now.year, now.month, now.day, tz=config['timezone'])
    since = until.subtract(days=1)

    for channel in config['channels']:
        for panel in channel['panels']:
            gc = GrafanaClient(url=panel['url'], token=panel['token'])
            gc.url = panel['url']
            gc.organization = panel['organization']
            gc.panel = panel['panel']
            gc.width = panel['width']
            gc.height = panel['height']
            gc.timezone = config['timezone']
            gc.since = since.int_timestamp * 1000
            gc.until = until.int_timestamp * 1000
            gc.labels = panel['labels']
            image = gc.get_image()

            f = tempfile.TemporaryFile()
            f.write(image)
            f.seek(0)

            mc = MattermostClient(base_url=config['url'], login=config['login'], password=config['password'])
            uploaded_files = mc.upload_files(channel['id'], {'image.png': f})
            mc.post_message(channel['id'], panel.get('message', ''), [list(d.values())[0] for d in uploaded_files])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
