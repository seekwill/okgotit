import sqlite3
import config

from flask import Flask, render_template, request, g, redirect, url_for
from twilio.rest import TwilioRestClient
from contextlib import closing

app = Flask(__name__)
app.config.from_object(__name__)

def connect_db():
    return sqlite3.connect(config.DATABASE)

def twillio_client():
    return TwilioRestClient(config.ACCOUNT_SID, config.AUTH_TOKEN)

@app.before_request
def before_request():
    g.db = connect_db()
    client = twillio_client()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

@app.route("/")
def hello():
  return "Private Domain"

@app.route("/users")
def users():
  cur = g.db.execute('SELECT id, name, mobilenum FROM user ORDER BY name')
  entries = [dict(id=row[0], name=row[1], mobilenum=row[2]) for row in cur.fetchall()]
  return render_template('users.html', entries=entries)

@app.route("/users/<id>")
def user(id=None):
  cur1 = g.db.execute('SELECT id, name, mobilenum FROM user WHERE id = ?', [id] )
  row1 = cur1.fetchall()
  cur2 = g.db.execute('SELECT cg.id, cg.name FROM callgroup AS cg INNER JOIN grouporder AS go ON cg.id = go.groupid WHERE go.userid = ? ORDER BY cg.name', [id] )
  callgroups = [dict(id=row2[0], name=row2[1]) for row2 in cur2.fetchall()]
  userinfo = dict(id=row1[0][0], name=row1[0][1], mobilenum=row1[0][2], callgroups=callgroups)
  return render_template('user.html', userinfo=userinfo)

@app.route("/users/add", methods=['POST'])
def adduser():
  g.db.execute('INSERT INTO user ( name, mobilenum ) VALUES ( ?, ? )', [request.form['name'], request.form['mobilenum']])
  g.db.commit()
  return redirect(url_for('users'))

@app.route("/users/<id>/del")
def deluser(id=None):
  g.db.execute('DELETE FROM user WHERE id = ?', [id])
  g.db.execute('DELETE FROM grouporder WHERE userid = ?', [id])
  g.db.commit()
  return redirect(url_for('users'))

@app.route("/users/<id>/addgroup/<gid>")
def addusertogroup(id=None,gid=None):
  g.db.execute('INSERT INTO grouporder ( groupid, userid ) VALUES ( ?, ? )', [gid, id])
  g.db.commit()
  return redirect(url_for('groups'))

@app.route("/users/<id>/removegroup/<gid>")
def removeuserfromgroup(id=None,gid=None):
  g.db.execute('DELETE FROM grouporder WHERE groupid = ? AND userid = ?', [gid, id])
  g.db.commit()
  return redirect(url_for('groups'))

@app.route("/groups")
def groups():
  cur = g.db.execute('SELECT id, name FROM callgroup ORDER BY name')
  entries = []
  for row in cur.fetchall():
    id = row[0]
    name = row[1]
    cur1 = g.db.execute('SELECT u.id, u.name FROM user AS u LEFT JOIN grouporder AS go ON u.id = go.userid AND go.groupid = ? WHERE go.id IS NULL', [id])
    adduser = [dict(id=row[0], name=row[1]) for row in cur1.fetchall()]
    cur1 = g.db.execute('SELECT u.id, u.name FROM user AS u INNER JOIN grouporder AS go ON u.id = go.userid AND go.groupid = ?', [id])

    users = []
    prevuser = 0
    for row in cur1.fetchall():
      users.append(dict(id=row[0], name=row[1],prevuser=prevuser))
      prevuser = row[0]
    entries.append(dict(id=id,name=name,adduser=adduser,users=users))
  return render_template('groups.html',  entries=entries)

@app.route("/groups/add", methods=['POST'])
def addgroup():
  g.db.execute('INSERT INTO callgroup ( name ) VALUES ( ? )', [request.form['name']])
  g.db.commit()
  return redirect(url_for('groups'))

@app.route("/groups/<gid>/switch/<id>/<pid>")
def groupswitchuser(id=None,pid=None,gid=None):
  # Not sure I like this, but it works now...
  cur1 = g.db.execute('SELECT userid, id FROM grouporder WHERE groupid = ? AND userid IN (?,?)', [gid, id, pid])
  rows = cur1.fetchall()
  g.db.execute('UPDATE grouporder SET userid = ? WHERE id = ?', [rows[0][0], rows[1][1]])
  g.db.execute('UPDATE grouporder SET userid = ? WHERE id = ?', [rows[1][0], rows[0][1]])
  g.db.commit()
  return redirect(url_for('groups'))

@app.route("/sms/will")
def smswill():

  message = client.sms.messages.create(body="Reminder Action Alert! Check your email.", to=smswill, from_=twilionumber)
  return message.sid

@app.route("/call/<callgroup>/reminder")
def callgroup():



  xmlfile = "{}/xml/reminder".format( config.XMLURL )
  call = client.calls.create(to=smsnum, from_=twilionumber, url=xmlfile)
  return 'hi'

@app.route("/xml/reminder", methods=['GET', 'POST'])
def reminder():
  return render_template('reminder.xml')

@app.route("/xml/response", methods=['GET', 'POST'])
def response():
  response = int(request.args.get('Digits', ''))
  return render_template('response.xml', response=response)

if __name__ == "__main__":
    app.debug = config.DEBUG
    app.run(host='0.0.0.0')
