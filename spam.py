from time import time
from rubpy import Client

spams = {}
msgs = 4 # Messages in
max = 5 # Seconds
ban = 300 # Seconds

async def is_spam(user_id: str, client: Client, object_guid: str):
    try:
        usr = spams[user_id]
        usr['messages'] += 1
    except IndexError:
        spams[user_id] = {'next_time': int(time()) + max, 'messages': 1, 'banned': 0}
        usr = spams[user_id]

    if usr['banned'] >= int(time()):
        return True
    else:
        if usr['next_time'] >= int(time()):
            if usr['messages'] >= msgs:
                spams[user_id]['banned'] = time() + ban
                user: dict = await client.get_user_info(user_id)
                await client.send_message(object_guid=object_guid,
                    message='❗️کاربر [{}]({}) به دلیل ارسال بیش حد از پیام به مدت {} دقیقه سکوت شد.'.format(str(user.first_name), user_id, round(ban/60)))
                #User is banned! alert him...
                return True
        else:
            spams[user_id]['messages'] = 1
            spams[user_id]['next_time'] = int(time()) + max
    return False