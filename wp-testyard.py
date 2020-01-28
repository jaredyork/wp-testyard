import os
import sys
import shutil
import fileinput
import urllib
import urllib3
from distutils.dir_util import copy_tree
from sultan.api import Sultan
import subprocess
import requests
from bs4 import BeautifulSoup
import zipfile

class App(object):
    def __init__(self):
        self.name = 'WP Testyard'

        if os.getuid() == 0:    
            self.display_welcome()
            self.main_menu()
        else:
            print('This program must be run in root.  Please run this with sudo.')

    def display_welcome(self):
        print('Welcome to ' + self.name)
        print('WP Sandboxes is an application compatible with Devilbox that allows for rapid reployment of WordPress instances.')
        print('')

    def main_menu(self):
        print('--- MAIN MENU ---')
        print('Please select an option below')
        print('')
        print('1. Create new WordPress instance')
        print('2. Remove existing WordPress instance')
        print('3. List available releases')
        print('')

        selected_option = -1
        valid = False
        while not valid:
            selected_option = int(input())
            if selected_option >= 0 and selected_option <= 3:
                valid = True

        if selected_option == 1:
            self.setup_release()
        if selected_option == 3:
            self.list_releases()

    def get_releases(self):
        page = requests.get('https://wordpress.org/download/releases/')

        soup = BeautifulSoup(page.text, 'html.parser')

        zip_releases = []

        count = 0

        for a in soup.find_all('a', href=True):
            if '.zip' in a['href'] and not '.md5' in a['href'] and not '.sha1' in a['href'] and not '-IIS' in a['href'] and not 'RC' in a['href'] and not 'beta' in a['href']:

                # Format the name
                
                # Start with href and remove domain
                release_name = a['href'].replace('https://wordpress.org/', '')
                
                # Get the file name
                file_name = release_name
                file_name_without_ext = release_name.replace('.zip', '')
                
                # Finish formatting release name
                
                # Convert dashes to spaces
                release_name = release_name.replace('-', ' ')
                # Remove .zip extension
                release_name = release_name.replace('.zip', '')
                # Properly capitalize WordPress
                release_name = release_name.replace('wordpress', 'WordPress')

                # Compile necessary data and append to zip_releases array
                release_data = dict()
                release_data['url'] = a['href']
                release_data['file_name'] = file_name
                release_data['file_name_without_ext'] = file_name_without_ext
                release_data['name'] = release_name

                zip_releases.append(release_data)

        # Remove the first release (labeled as Latest Release on WordPress.org) since it's a duplicate
        zip_releases.pop(0)

        return zip_releases

    def list_releases(self):
        release_data = self.get_releases()
        for release in release_data:
            print(release['name'])

    def download(self, url, dest_path):
        with open(dest_path, "wb") as file:
            response = requests.get(url)
            file.write(response.content)

    def find_append_to_file(self, filename, find, insert):
        """Find and append text in a file."""
        for line in fileinput.FileInput(filename, inplace=1):
            if find in line:
                line = line.replace(line, line + insert)
            print(line, end='')

    def setup_release(self):
        release_data = self.get_releases()
        print('Please enter a release version:')
        print('')
        release_data_specified = None
        valid = False
        while not valid:
            version = input()

            for release in release_data:
                # Get the release name minus 'WordPress '
                release_name_as_version = release['name']
                release_name_as_version = release_name_as_version.replace('WordPress ', '')

                if version == release_name_as_version:
                    release_data_specified = release
                    valid = True

        # Create a releases directory in WP Sandboxes
        if not os.path.isdir('./releases'):
            os.mkdir('./releases')

        # Check if the release already exists in WP Sandboxes
        if os.path.isdir('./releases/' + release_data_specified['file_name_without_ext']):
            print('Release already downloaded, skipping download.')
        else:
            # Download the release
            print('Downloading ' + release_data_specified['file_name'])
            self.download(release_data_specified['url'], './releases/' + release_data_specified['file_name'])
            print('Finished downloading ' + release_data_specified['file_name'])

            # Extract the release
            print('Starting extraction on ' + release_data_specified['file_name'])
            with zipfile.ZipFile('./releases/' + release_data_specified['file_name'], 'r') as zip_ref:
                zip_ref.extractall('./releases/' + release_data_specified['file_name_without_ext'])
                print('Extracted ' + release_data_specified['file_name'])

        
        print('')
        print('What would you like the vhost name of this instance to be? (without .loc)')
        vhost_name = input()

        # Backup /etc/hosts
        # Create local temp directory if it doesn't exist
        if not os.path.isdir('./temp'):
            os.mkdir('./temp')

        # Copy /etc/hosts to our temp directory
        try:
            shutil.copyfile('/etc/hosts', './temp/hosts')            
        except shutil.Error as e:
            print(e)
        else:
            print('Backed up /etc/hosts')

        # Add a line to /etc/hosts
        if '# WP Sandboxes' in open('/etc/hosts').read():
            print("WP Sandboxes comment exists in /etc/hosts, proceeding...")

        else:
            print("WP Sandboxes comment does not exist in /etc/hosts, adding comment...")

            with open('/etc/hosts', 'a') as f:
                f.write('\n# WP Sandboxes\n')
                print("Comment added.")

        # Write entry into /etc/hosts
        self.find_append_to_file('/etc/hosts', '# WP Sandboxes', '127.0.0.1 ' + vhost_name + '.loc\n')

        # Create an instance directory in ~/devilbox/data
        devilbox_dir = os.path.expanduser('~') + '/devilbox'
        instance_dir = os.path.expanduser('~') + '/devilbox/data/www/' + vhost_name
        instance_htdocs_dir = instance_dir + '/htdocs'
        if not os.path.isdir(instance_dir):
            os.mkdir(instance_dir)
            print('Created instance directory')

        if not os.path.isdir(instance_htdocs_dir):
            os.mkdir(instance_htdocs_dir)
            print('Created htdocs directory in instance directory')

        # Copy over WordPress files from extracted directory to our instance folder
        copy_tree('./releases/' + release_data_specified['file_name_without_ext'] + '/wordpress', instance_htdocs_dir)

        print("Executing script from: " + os.path.dirname(os.path.abspath(__file__)) + '/add-database.sh')

        # Create an override docker-compose.yml file
        """
        if not os.path.isfile(devilbox_dir + '/docker-compose.override.yml'):
            with open(devilbox_dir + '/docker-compose.override.yml', 'w+') as f:
                f.write('version: \'2.1\'\n')
                f.write('stdin_open: true\n')
                f.write('tty: true\n')
                f.close()
        """

        # Create a database in Devilbox
        database_name = vhost_name
        database_name = database_name.replace('-', '_')

        p = subprocess.call('sudo sh ' + os.path.dirname(os.path.abspath(__file__)) + '/add-database.sh ' + database_name, shell=True)

        wp_host = 'http://' + vhost_name + '.loc:80'

        values = {
            'dbname': vhost_name,
            'uname': 'root',
            'pwd': '',
            'dbhost': database_name + '.loc',
            'prefix': 'wp_'
        }

        install_questions_form_url = wp_host + '/wp-admin/setup-config.php?step=2'
        print('INSTALL QUESTIONS FORM URL: ' + install_questions_form_url)
        
        req = urllib.request.Request(url=wp_host + '/wp-admin/setup-config.php?step=2',
            data=urllib.parse.urlencode(values).encode(),
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.95 Safari/537.36'})
        response = urllib.request.urlopen(req)

        print(response)

        print('All done!')

app = App()