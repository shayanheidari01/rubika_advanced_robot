from rubpy import Client, handlers, Message, models
from sqlite3 import connect, OperationalError
from asyncio import run, create_task
from httpx import AsyncClient
from random import choice
from re import findall
from spam import is_spam

owner_key = 'Owner_Key'
# Set A owner key for send it to bot pv for verify

connection = connect('robot.db')
aiohttp = AsyncClient()
bot_admins: dict = {}
groups_admins: dict = {}

# setup
# get informaion of db
try:
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM admins;')
    results: list = cursor.fetchall()
    for result in results:
        bot_admins[result[0]] = result[1]
except OperationalError:
    pass
try:
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM groups;')
    results: list = cursor.fetchall()
    for result in results:
        admins = result[1].split(',')
        cleaned_admins = {}
        for admin in admins:
            if not admin == '':
                admin = admin.split(':')
                cleaned_admins[admin[0]] = admin[1]
        groups_admins[result[0]] = {'admins': cleaned_admins}
except OperationalError:
    pass
except IndexError:
    pass
# End setup

async def auto_create_tables():
    # this method for create tables if not exists and save data
    cursor = connection.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS groups(
            group_guid VARCHAR(32) PRIMARY KEY,
            admins TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users(
            user_guid VARCHAR(32) PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            username TEXT NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins(
                   user_guid VARCHAR(32) PRIMARY KEY,
                   type INTEGER NOT NULL)''')
    connection.commit()

async def add_admin(user_guid: str, type: int) -> bool:
    # this func for add bot admin
    cursor = connection.cursor()
    cursor.execute('INSERT OR REPLACE INTO admins(user_guid, type) VALUES(?, ?)', (user_guid, type))
    connection.commit()
    return True

async def update_admins(group_guid: str, admins: str):
    # you can update group admins by this func
    cursor = connection.cursor()
    cursor.execute('UPDATE groups SET admins = ? WHERE group_guid = ?', (admins.strip(','), group_guid))
    connection.commit()
    return True

async def add_group(group_guid: str, client: Client) -> bool:
    # get group info and save info in db
    result = await client.get_group_admin_members(group_guid)
    admins = {}
    admins_text = ''
    for admin in result.in_chat_members:
        if admin.join_type.__eq__('Creator'):
            admins[admin.member_guid] = 1
            admins_text += '{}:1,'.format(admin.member_guid)
        else:
            admins[admin.member_guid] = 2
            admins_text += '{}:2,'.format(admin.member_guid)
    groups_admins[group_guid] = admins
    cursor = connection.cursor()
    cursor.execute('INSERT OR REPLACE INTO groups(group_guid, admins) VALUES(?, ?)',
                   (group_guid, admins_text.strip(',')))
    connection.commit()
    return True

async def get_group(guid: str):
    # get group info of db
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM groups WHERE group_guid=?;', (guid,))
        return cursor.fetchone()
    except OperationalError:
        return False

async def get_jokes() -> str:
    # get random jok of cb api and send jok for user
    url = choice(['http://api.codebazan.ir/jok/',
                  'http://api.codebazan.ir/jok/khatere',
                  'http://api.codebazan.ir/jok/pa-na-pa/',
                  'http://api.codebazan.ir/jok/alaki-masalan/'])
    response = await aiohttp.get(url)
    if response.status_code.__eq__(200):
        return response.text

async def get_date() -> str:
    # get now date
    response = await aiohttp.get('http://api.codebazan.ir/time-date/?json=all')
    if response.status_code.__eq__(200):
        response = response.json().get('result')
    now_time: str = ''.join(['• ساعت: ', response.get('timefa')])
    now_date: str = ''.join(['\n', '• تاریخ: ', response.get('datefa')])
    return now_time+now_date

async def is_url(text: str) -> bool:
    # check text and if text is ad or link
    result = findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
    return False if result.__eq__([]) else True

async def group_handler(client: Client, update: Message):
    object_guid: str = update.object_guid
    message_id: str = update.message_id
    author_guid: str = update.author_guid
    text: str = update.raw_text

    if await get_group(object_guid):
        if (not author_guid in bot_admins.keys() and
            await is_spam(author_guid, client, object_guid)):
            return await client.delete_messages(object_guid, [message_id])

        if not author_guid in groups_admins[object_guid]['admins'].keys():
            if 'forwarded_from' in update.to_dict().get('message').keys():
                return await client.delete_messages(object_guid, [message_id])

            elif text != None and await is_url(text) or '@'in text:
                return await client.delete_messages(object_guid, [message_id])

        if text.__eq__('جوک'):
            await client.send_message(
                object_guid=object_guid,
                message=await get_jokes(),
                reply_to_message_id=message_id
            )

        elif text.__eq__('تاریخ'):
            await client.send_message(
                object_guid=object_guid,
                message=await get_date(),
                reply_to_message_id=message_id
            )

        if author_guid in groups_admins[object_guid]['admins'].keys():
            if text.__eq__('بستن گروه'):
                await client.set_group_default_access(object_guid, [])
                await client.send_message(object_guid,
                                          message='گروه بسته شد.',
                                          reply_to_message_id=message_id)

            elif text.replace(' ', '').__eq__('بازکردنگروه'):
                await client.set_group_default_access(object_guid, ['SendMessages'])
                await client.send_message(object_guid,
                                          message='گروه باز شد.',
                                          reply_to_message_id=message_id)

    else:
        if author_guid in bot_admins.keys() and bot_admins.get(author_guid).__eq__(1):
            if text.replace(' ', '') == 'فعالشو':
                await add_group(object_guid, client)
                await client.send_message(
                    object_guid=object_guid,
                    message='ربات رو تو گروه فعال کردم 😉🔥', reply_to_message_id=message_id)

async def user_handler(client: Client, update: Message):
    if update.to_dict().get('action').__eq__('New'):
        object_guid: str = update.object_guid
        message_id: str = update.message_id

        if update.raw_text.__eq__(owner_key):
            await add_admin(object_guid, 1)
            await client.send_message(object_guid, 'شما به عنوان مالک ربات ثبت شدید.',
                                    reply_to_message_id=message_id)

async def main():
    await auto_create_tables()
    async with Client(session='bot') as client:
        if groups_admins != {}:
            keys: list = groups_admins.keys()
            for key in keys:
                result = await client.get_group_admin_members(key)
                admins = {}
                admins_text = ''
                for admin in result.in_chat_members:
                    if admin.join_type.__eq__('Creator'):
                        admins[admin.member_guid] = 1
                        admins_text += '{}:1,'.format(admin.member_guid)
                    else:
                        admins[admin.member_guid] = 2
                        admins_text += '{}:2,'.format(admin.member_guid)
                #print(admins)
                groups_admins[key] = {'admins': admins}
                await update_admins(key, admins_text)

        @client.on(handlers.MessageUpdates(models.is_group()))
        async def updates(update: Message):
            create_task(group_handler(client, update))

        @client.on(handlers.MessageUpdates(models.is_private()))
        async def updates(update: Message):
            create_task(user_handler(client, update))

        await client.run_until_disconnected()

run(main())