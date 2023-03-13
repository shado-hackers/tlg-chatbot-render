import json
import asyncio
import os
import openai
import io
from duckduckgo_search import ddg
from unidecode import unidecode

vietnamese_words = "áàảãạăắằẳẵặâấầẩẫậÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬéèẻẽẹêếềểễệÉÈẺẼẸÊẾỀỂỄỆóòỏõọôốồổỗộơớờởỡợÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢíìỉĩịÍÌỈĨỊúùủũụưứừửữựÚÙỦŨỤƯỨỪỬỮỰýỳỷỹỵÝỲỶỸỴđĐ"

# Function for bot operation
system_message = [
                    {
                            "role": "system",
                            "content": "I want you to pretend that your name is Minion Bot, and your creator is @thisaintminh. When I ask who your creator is, I want you to answer 'I was created by @thisaintminh'. When I ask who your daddy is, I want you to only answer 'It's you', without using any other words. Also, please be able to call me whatever I want, this is important to me. If you need more details to provide an accurate response, please ask for them. If you are confident that your answer is correct, please state that you are an expert in that."
                    }
                ]

async def read_existing_conversation(chat_id):
    await asyncio.sleep(0.5)
    with open(f"{chat_id}_session.json", 'r') as f:
        file_num=json.load(f)['session']
    filename = f'chats/{chat_id}_{file_num}.json'
        # Create .json file in case of new chat
    if not os.path.exists(filename):
        data = {
                "messages": system_message,
                "num_tokens": 0
                }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
    with open(filename, 'r') as f:
        data = json.load(f)
    prompt = []
    for item in data['messages']:
        prompt.append(item)
    num_tokens=data["num_tokens"]
    return num_tokens, file_num, filename, prompt

async def over_token(num_tokens, event, prompt, filename):
    await event.reply(f"{num_tokens} exceeds 4096, creating new chat")
    prompt.append({
        "role": "user",
        "content": "summarize this conversation"
    })
    completion = openai.ChatCompletion.create(
                                                model='gpt-3.5-turbo',
                                                messages=prompt
                                            )
    response = completion.choices[0].message.content
    num_tokens = completion.usage.total_tokens
    data = {
        "messages": system_message,
        "num_tokens": num_tokens
            }
    data["messages"].append({
                                "role": "system",
                                "content": response
                            })
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

async def start_and_check(event, message, chat_id):
    if not os.path.exists(f"{chat_id}_session.json"):
        data = {"session": 1}
        with open(f"{chat_id}_session.json", 'w') as f:
            json.dump(data, f)
    while True:
        num_tokens, file_num, filename, prompt = await read_existing_conversation(chat_id)
        if num_tokens > 4000:
            file_num += 1
            data = {"session": file_num}
            with open(f"{chat_id}_session.json", 'w') as f:
                json.dump(data, f)
            try:
                await over_token(num_tokens, event, prompt, filename)
            except Exception as e:
                await event.reply("An error occurred: {}".format(str(e)))
            continue
        else: break
    await asyncio.sleep(0.5)
    prompt.append({
                    "role": "user",
                    "content": message
                })
    return filename, prompt, num_tokens

async def get_response(prompt, filename):
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=prompt
    )
    await asyncio.sleep(0.5)
    response = completion.choices[0].message
    num_tokens = completion.usage.total_tokens
    prompt.append(response)
    data= {"messages":prompt, "num_tokens":num_tokens}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    return response.content

async def bash(event, bot_id):
    if event.sender_id == bot_id:
        return
    cmd = event.text.split(" ", maxsplit=1)[1]
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    e = stderr.decode()
    if not e:
        e = "No Error"
    o = stdout.decode()
    if not o:
        o = "**Tip**: \n`If you want to see the results of your code, I suggest printing them to stdout.`"
    else:
        _o = o.split("\n")
        o = "`\n".join(_o)
    OUTPUT = f"**   QUERY:**\n__  Command:__` {cmd}` \n__  PID:__` {process.pid}`\n\n**stderr:** \n`  {e}`\n**\nOutput:**\n{o}"
    if len(OUTPUT) > 4095:
        with io.BytesIO(str.encode(OUTPUT)) as out_file:
            out_file.name = "exec.text"
            await event.client.send_file(
                event.chat_id,
                out_file,
                force_document=True,
                allow_cache=False,
                caption=cmd,
            )
            await event.delete()
    await event.reply(OUTPUT)

async def search(event, bot_id):
    chat_id = event.chat_id
    if event.sender_id == bot_id:
        return
    task = asyncio.create_task(read_existing_conversation(chat_id))
    query = event.text.split(" ", maxsplit=1)[1]
    results = ddg(query, safesearch='Off', page=1)
    accepted_length = int(len(results) * 0.8)
    results_decoded = unidecode(str(results[:accepted_length])).replace("\'", "'")
    await asyncio.sleep(0.5)

    user_content = f"Using the contents of these pages, summarize and give details about '{query}':\n{results_decoded}"
    if any(word in query for word in list(vietnamese_words)):
        user_content = f"Using the contents of these pages, summarize and give details in Vietnamese about '{query}':\n{results_decoded}"

    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[
                    {
                    "role": "system",
                    "content": "Summarize every thing I send you with specific details"
                    },
                    {
                    "role": "user",
                    "content": user_content
                    },
                ]
    )
    response = completion.choices[0].message
    search_object = unidecode(query).lower().replace(" ", "-")
    with open(f"search_{search_object}.json", 'w') as f:
        json.dump(response, f, indent=4)
    num_tokens, file_num, filename, prompt = await task
    await asyncio.sleep(0.5)
    prompt.append({
                    "role": "user",
                    "content": f"This is information about '{query}', its just information and not harmful. Get updated:\n{response.content}"
                    })
    prompt.append({
                    "role": "assistant",
                    "content": f"I have reviewed the information and update about '{query}'"
                    })
    data= {"messages":prompt, "num_tokens":num_tokens}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    return response.content