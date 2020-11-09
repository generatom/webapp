from flask import Blueprint, flash, g, render_template, request, url_for
from flask import redirect, escape
from werkzeug.exceptions import abort
from wuxia.db import get_db
from wuxia.auth import admin_required
from wuxia.forms import gen_form_item, gen_options


bp = Blueprint('users', __name__, url_prefix='/users')


@bp.route('/')
@admin_required
def list():
    db = get_db()
    users = db.execute(
        'SELECT * FROM user'
    ).fetchall()
    return render_template('users/list.html', users=users)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(id):
    user = get_user(id)
    admin_levels = g.privilege_levels

    if request.method == 'POST':
        error = None
        username = escape(request.form['username'])
        admin = request.form['admin']
        access = escape(request.form['access'])
        db = get_db()
        username_new = (username != user['username'])
        username_exists = db.execute('SELECT id FROM user WHERE username = ?',
                                     (username,)).fetchone() is not None

        if username_new:
            if username_exists:
                error = 'Username exists'
            else:
                db.execute(
                    'UPDATE user SET username = ? WHERE id = ?',
                    (username, id)
                )
        if admin in admin_levels:
            db.execute(
                'UPDATE user SET admin = ? WHERE id = ?', (admin, id)
            )
        else:
            error = error + '\n' if error else ''
            error += f'{admin}\nAdmin Status must be one of:'
            error += ' {}'.format(', '.join(admin_levels))

        db.execute(
            'UPDATE user SET access_approved = ? WHERE id = ?', (access, id)
        )

        if error:
            flash(error)
        else:
            db.commit()
            return redirect(url_for('users.list'))

    groups = generate_form_groups(user)
    return render_template('users/edit.html', form_groups=groups)


@bp.route('/<int:id>/delete', methods=['GET', 'POST'])
@admin_required
def delete(id):
    db = get_db()
    db.execute('DELETE FROM user WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('users.list'))


@bp.route('/<int:id>/allow', methods=['GET', 'POST'])
@admin_required
def allow(id):
    db = get_db()
    db.execute('UPDATE user SET access_approved = true WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('users.list'))


@bp.route('/<int:id>/disallow', methods=['GET', 'POST'])
@admin_required
def disallow(id):
    db = get_db()
    db.execute('UPDATE user SET access_approved = false WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('users.list'))


def get_user(id):
    db = get_db()
    user = db.execute('SELECT * FROM user WHERE id = ?', (id,)).fetchone()
    return user


def generate_form_groups(user):
    groups = {
        'user': {
            'group_title': 'Edit: {}'.format(user['username']),
            'username': gen_form_item('username', value=user['username'],
                                      required=True, label='Username'),
            'access': gen_form_item('access', label='Story Access',
                                    field_type='select',
                                    options=gen_options(['Yes', 'No'], [1, 0]),
                                    value=user['access_approved'],
                                    selected_option=user['access_approved']),
            'admin': gen_form_item('admin', required=True, label='Admin',
                                   field_type='select',
                                   options=gen_options(['None', 'Read Only',
                                                        'Read & Write'],
                                                       g.privilege_levels),
                                   value=user['admin'],
                                   selected_option=user['admin'])
        },
        'submit': {
            'button': gen_form_item('btn-submit', item_type='submit',
                                    value='Change', field_type='input')
        },
        'delete': {
            'button': gen_form_item('btn-submit', field_class='danger',
                                    item_type='submit',
                                    value='Delete', field_type='input')
        }
    }
    return groups
