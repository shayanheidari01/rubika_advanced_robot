from rubpy import Client, handlers, Message, models
from sqlite3 import connect, OperationalError
from asyncio import run, create_task
from httpx import AsyncClient
from random import choice
from re import findall
from spam import is_spam

owner_key = 'Owner_Key'

connection = connect('robot.db')
aiohttp = AsyncClient()
bot_admins: dict = {}
groups_admins: dict = {}

# setup
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

async def auto_create_tables():
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
    cursor = connection.cursor()
    cursor.execute('INSERT OR REPLACE INTO admins(user_guid, type) VALUES(?, ?)', (user_guid, type))
    connection.commit()
    return True

async def update_admins(group_guid: str, admins: str):
    cursor = connection.cursor()
    cursor.execute('UPDATE groups SET admins = ? WHERE group_guid = ?', (admins.strip(','), group_guid))
    connection.commit()
    return True

async def add_group(group_guid: str) -> bool:
    cursor = connection.cursor()
    cursor.execute('INSERT OR REPLACE INTO groups(group_guid) VALUES(?)', (group_guid,))
    connection.commit()
    return True

async def get_group(guid: str):
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM groups WHERE group_guid=?;', (guid,))
        return cursor.fetchone()
    except OperationalError:
        return False

async def get_jokes() -> str:
    url = choice(['http://api.codebazan.ir/jok/',
                  'http://api.codebazan.ir/jok/khatere',
                  'http://api.codebazan.ir/jok/pa-na-pa/',
                  'http://api.codebazan.ir/jok/alaki-masalan/'])
    response = await aiohttp.get(url)
    if response.status_code.__eq__(200):
        return response.text

async def is_url(text: str) -> bool:
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

        if not author_guid in bot_admins.keys():
            if await is_url(text) or '@'in text:
                return await client.delete_messages(object_guid, [message_id])

            elif 'forwarded_from' in update.to_dict().get('message').keys():
                return await client.delete_messages(object_guid, [message_id])

        if text.__eq__('جوک'):
            await client.send_message(
                object_guid=object_guid,
                message=await get_jokes(),
                reply_to_message_id=message_id
            )

    else:
        if author_guid in bot_admins.keys() and bot_admins.get(author_guid).__eq__(1):
            if text.replace(' ', '') == 'فعالشو':
                await add_group(object_guid)
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
                groups_admins[key] = admins
                await update_admins(key, admins_text)

        @client.on(handlers.MessageUpdates(models.is_group()))
        async def updates(update: Message):
            create_task(group_handler(client, update))

        @client.on(handlers.MessageUpdates(models.is_private()))
        async def updates(update: Message):
            create_task(user_handler(client, update))

        await client.run_until_disconnected()

run(main())