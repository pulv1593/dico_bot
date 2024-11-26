import discord
import re
import yt_dlp as youtube_dl
import asyncio
from discord.ext import commands
from dico_token import Token
 
# bot intents 정의
intents = discord.Intents.default()
intents.message_content = True

# bot 기본 세팅, 명령어 앞에 !로 시작하게 설정.
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description='디스코드 입장을 위한 테스트 코드',
    intents=intents,
)

#봇 이벤트 처리 함수 모음 
@bot.event
async def on_ready():
    print('{0.user} 봇을 실행합니다.'.format(bot))
 
# 명령어 함수 모음
# 노래봇을 음성채팅에 데려오는 명령어
@bot.command(aliases=['입장'])
async def join(ctx):
    embed = discord.Embed(title = "디스코드 봇 도우미(개발용)", description = "음성 채널 개발용 디스코드 봇",color=0x00ff56)
    channel = ctx.author.voice.channel
    
    if ctx.author.voice is None:
        embed.add_field(name=':exclamation:', value="음성 채널에 유저가 존재하지 않습니다. 1명 이상 입장해주세요.")
        await ctx.send(embed=embed)
        raise commands.CommandInvokeError("사용자가 존재하는 음성 채널을 찾지 못했습니다.")
    
    if ctx.voice_client is not None:
        embed.add_field(name=":robot:",value="사용자가 있는 채널로 이동합니다.", inline=False)
        await ctx.send(embed=embed)
        print("음성 채널 정보: {0.author.voice}".format(ctx))
        print("음성 채널 이름: {0.author.voice.channel}".format(ctx))
        return await ctx.voice_client.move_to(channel)
        
    await channel.connect()

#노래봇을 음성채널에서 내보내는 명령어 
@bot.command(aliases=['나가기'])
async def out(ctx):
    try:
        embed = discord.Embed(color=0x00ff56)
        embed.add_field(name=":regional_indicator_b::regional_indicator_y::regional_indicator_e:",value=" {0.author.voice.channel}에서 내보냈습니다.".format(ctx),inline=False)
        await bot.voice_clients[0].disconnect()
        await ctx.send(embed=embed)
    except IndexError as error_message:
        print(f"에러 발생: {error_message}")
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":grey_question:",value="{0.author.voice.channel}에 유저가 존재하지 않거나 봇이 존재하지 않습니다.\\n다시 입장후 퇴장시켜주세요.".format(ctx),inline=False)
        await ctx.send(embed=embed)
    except AttributeError as not_found_channel:
        print(f"에러 발생: {not_found_channel}")
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:",value="봇이 존재하는 채널을 찾는 데 실패했습니다.")
        await ctx.send(embed=embed)

# URL 유효성 검사 함수
def is_valid_url(url):
    regex = r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|https?://(?:www\.)?youtu\.be/[\w-]+)'
    return re.match(regex, url) is not None

#url, 키워드로 검색하여 노래를 재생하는 명령어.
@bot.command(aliases=['재생'])
async def play(ctx, *, search: str):
  if ctx.author.voice is None:
    await ctx.send("음성 채널에 입장한 후 명령어를 사용해주세요.")
    return

  if ctx.voice_client is None:
    await ctx.invoke(bot.get_command('join'))

  ytdl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extractaudio': True,
    'noplaylist': True,
    'default_search': 'ytsearch',
    'duration': '<600',  # 10분 이하 동영상만 검색(성능 최적화)
    'source_address': '0.0.0.0',  # IPv4 연결 사용
  }
  ytdl = youtube_dl.YoutubeDL(ytdl_opts)

  # "검색 중입니다!" 메시지 보내기
  loading_message = await ctx.send("🔍 노래를 찾고있어요..! 조금만 기다려주세요...")
  
  try:
    #url이 직접 주어진 경우 URL을 바로 처리하여 재생
    if is_valid_url(search):
      # 유효한 URL이면 바로 재생
      info = ytdl.extract_info(search, download=False)
      url = info.get('url')
      title = info.get('title', '알 수 없는 제목')

      embed = discord.Embed(title=":musical_note: 재생 중", description=f"**{title}**", color=0x1DB954)
      await ctx.send(embed=embed)

      FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
      }

      if not ctx.voice_client.is_playing():
        audio_source = discord.FFmpegOpusAudio(url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(audio_source, after=lambda e: print(f"재생이 종료되었습니다: {e}"))
      else:
        await ctx.send("노래가 이미 재생 중입니다.")
    else:
      #키워드가 입력된 경우 검색 수행
      info = ytdl.extract_info(f"ytsearch3:{search}", download=False)
      entries = info.get('entries', [])
        
      if not entries:
        await loading_message.edit(content="검색 결과가 없습니다. 다른 키워드로 시도해주세요.")
        return
        
      # 검색결과를 discord 메세지로 출력
      embed = discord.Embed(title="검색 결과", description="원하는 곡 번호를 입력해주세요!",  color=0x1DB954)
      for i, entry in enumerate(entries[:3]):  # 최대 4개 출력
        embed.add_field(
          name=f"{i+1}. {entry['title']}", 
          value="\u200b",  # 빈 줄 표시 (Discord가 value를 요구할 경우)
          inline=False
        )
    
      # 기존 메시지 수정
      await loading_message.edit(content=None, embed=embed)
        
      # 사용자 입력 대기
      def check(msg):
        return msg.author == ctx.author and msg.content.isdigit() and 1 <= int(msg.content) <= len(entries[:4])
        
      try:
        msg = await bot.wait_for('message', check=check, timeout=60.0)  # 30초 대기
        selection = int(msg.content) - 1
        selected_entry = entries[selection]
      except asyncio.TimeoutError:
        await ctx.send("시간 초과로 명령어가 취소되었습니다.")
        return  
          
      # 선택된 음원 재생
      url = selected_entry.get('url') or selected_entry.get('webpage_url')
      title = selected_entry.get('title', '알 수 없는 제목')

      embed = discord.Embed(title=":musical_note: 재생 중", description=f"**{title}**", color=0x1DB954)
      await ctx.send(embed=embed)

      # FFMPEG 옵션 설정
      FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',  # 네트워크 안정성 향상
        'options': '-vn',  # 비디오 비활성화
      }

      # Opus 형식으로 오디오 스트리밍
      if not ctx.voice_client.is_playing():
        audio_source = discord.FFmpegOpusAudio(url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(audio_source, after=lambda e: print(f"재생이 종료되었습니다: {e}"))
      else:
        await ctx.send("노래가 이미 재생 중입니다.")
  except Exception as e:
    await ctx.send("음악을 재생할 수 없습니다. 링크 또는 키워드를 확인해주세요.")
    print(f"에러 발생: {e}")

#노래 재생을 끝내고 내보내기
@bot.command(aliases=['멈춤', '정지'])
async def stop(ctx):
    if ctx.voice_client is None:
        embed = discord.Embed(color=0xf66c24)
        embed.add_field(name=":x:", value="봇이 음성 채널에 연결되어 있지 않습니다.")
        await ctx.send(embed=embed)
        return

    # 음악이 재생 중이면 멈추기
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()

    # 음성 채널에서 봇을 나가게 함
    await ctx.voice_client.disconnect()

    embed = discord.Embed(color=0x00ff56)
    embed.add_field(name=":stop_button:", value="음악을 멈추고 음성 채널에서 나갔습니다.", inline=False)
    await ctx.send(embed=embed)
 
bot.run(Token)