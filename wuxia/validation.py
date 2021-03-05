from wuxia.db import get_db
from flask import current_app
from flask.cli import with_appcontext
import click
import docker
from docker.errors import ImageNotFound, ContainerError
from jinja2 import Template
import os
from string import ascii_letters
from random import choices


client = docker.from_env()


def check_docker_images(image_name='validator:latest', path=None, dockerfile_template=None):
    image = None
    dockerfile = 'docker_files/Dockerfile'
    dockerfile_template = dockerfile_template if dockerfile_template else 'docker_files/Dockerfile.j2'

    try:
        image = client.images.get(image_name)
        print(image)
    except ImageNotFound:
        with current_app.open_resource(dockerfile_template) as f:
            template = Template(f.read())

        completed_template = template.render(uid=str(os.getuid()))
        print(completed_template)
        write_path = os.path.join(current_app.root_path, dockerfile)
        with open(write_path, 'w') as f:
            f.write(completed_template)

        path = path if path else os.getcwd()
        image, logs = client.images.build(path=path, tag=image_name, rm=True, dockerfile=dockerfile)
        print(f'{image} built.')

    return image


def generate_entrypoint(user_id, verifier_filename, template='docker_files/validate.j2',
                        destination='docker_files/validate.sh'):
    write_destination = os.path.join(current_app.root_path, destination)
    with current_app.open_resource(template) as f1, open(write_destination, 'w') as f2:
        entrypoint = Template(f1.read())
        f2.write(entrypoint.render(user_id=user_id, verifier_filename=verifier_filename))

    os.chmod(destination, 0o755)


def get_filename(row, column='file_name'):
    return row[0][column]


class Validator:
    def __init__(self, challenge_id, user_id):
        db = get_db()
        self.challenge_id = challenge_id
        self.user_id = user_id
        self.verifier_filename = db.get_challenges(challenge_id, ['verifier_filename'])[0]['verifier_filename']
        self.verifiers = db.get_challenge_files(challenge_id, file_types=['verifier'], columns=['file_name'])
        self.results = db.get_challenge_files(challenge_id, file_types=['result'], columns=['file_name'])
        self.user_file = db.get_challenge_files(challenge_id, user_id=user_id, file_types=['user'],
                                                columns=['file_name'])
        self.verification_script = 'validate.sh'
        generate_entrypoint(self.user_id, self.verifier_filename, destination=os.path.join('docker_files/',
                                                                                           self.verification_script))
        self.image = check_docker_images()

    def generate_user_output(self,  image=None):
        image = image if image else self.image
        challenge_folder = os.path.join(current_app.instance_path, 'challenges/', str(self.challenge_id))
        volumes = {
            challenge_folder: {
                'bind': '/tmp/validation/files',
                'mode': 'rw'
            }
        }
        container_name = 'validate_c' + str(self.challenge_id) + '_u' + str(self.user_id) + '_' +\
                         ''.join(choices(ascii_letters, k=8))

        results = error = None
        try:
            results = client.containers.run(image.tags[0], f'./{self.verification_script}', volumes=volumes,
                                            name=container_name)
        except ContainerError as e:
            error = client.containers.get(container_name).logs()
            error = error.decode().splitlines()

        except Exception as e:
            error = e

        return results, error

    def compare_results(self, user_results):
        result_file = get_filename(self.results)
        with open(result_file) as f:
            results = f.read()

        return user_results.strip() == results.strip() if user_results else False
    
    def validate(self):
        results, error = self.generate_user_output()
        return self.compare_results(results), error


@click.command('check-validator')
@with_appcontext
def check_validator():
    v = Validator(1, 1)
    print(v.validate())


def init_app(app):
    app.cli.add_command(check_validator)
