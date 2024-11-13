import nextcord
from nextcord.ext import commands
import requests
import random
import asyncio

TOKEN = 'token' #It has been changed, Get a new token from the developers portal

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Store ongoing quizzes with user data
user_sessions = {}

# Define category and difficulty choices
CATEGORY_CHOICES = {
    "Any Category": "any",
    "General Knowledge": 9,
    "Entertainment: Books": 10,
    "Entertainment: Film": 11,
    "Entertainment: Music": 12,
    "Entertainment: Musicals & Theatres": 13,
    "Entertainment: Television": 14,
    "Entertainment: Video Games": 15,
    "Entertainment: Board Games": 16,
    "Science & Nature": 17,
    "Science: Computers": 18,
    "Science: Mathematics": 19,
    "Mythology": 20,
    "Sports": 21,
    "Geography": 22,
    "History": 23,
    "Politics": 24,
    "Art": 25,
    "Celebrities": 26,
    "Animals": 27,
    "Vehicles": 28,
    "Entertainment: Comics": 29,
    "Science: Gadgets": 30,
    "Entertainment: Japanese Anime & Manga": 31,
    "Entertainment: Cartoon & Animations": 32
}
DIFFICULTY_CHOICES = ["easy", "medium", "hard"]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.reference and message.reference.cached_message:
        # Check if the message is a reply to the bot's previous question
        original_message = message.reference.cached_message
        if original_message.author == bot.user and original_message.content.startswith("**Question"):
            # Call the 'answer' function with the user's answer
            await answer(message.channel, message.content, message.author)
            return

    # Handle other message events as needed
    await bot.process_commands(message)

@bot.slash_command(name="quiz")
async def quiz(interaction: nextcord.Interaction):
    await interaction.response.send_message("Welcome to Trivia! Use /quiz start to begin.", ephemeral=True)

@quiz.subcommand(name="start")
async def start(
    interaction: nextcord.Interaction,
    category: str = nextcord.SlashOption(
        name="category",
        description="Select a category",
        choices={name: str(id) for name, id in CATEGORY_CHOICES.items()}  # Maps name to category ID as string
    ),
    difficulty: str = nextcord.SlashOption(
        name="difficulty",
        description="Select a difficulty",
        choices=DIFFICULTY_CHOICES
    ),
    number_of_questions: int = 5
):
    # Fetch questions from Open Trivia Database API
    url = f"https://opentdb.com/api.php?amount={number_of_questions}&category={category}&difficulty={difficulty}&type=multiple"
    response = requests.get(url)
    data = response.json()

    if data['response_code'] != 0:
        await interaction.response.send_message("Sorry, I couldn't fetch questions for that category or difficulty.")
        return

    # Initialize user session for the quiz
    user_sessions[interaction.user.id] = {
        "questions": data['results'],
        "current_question": 0,
        "score": 0,
        "answered": False
    }

    # Get the category name from the CATEGORY_CHOICES dictionary
    category_name = next((name for name, id in CATEGORY_CHOICES.items() if str(id) == category), "Unknown Category")

    await interaction.response.send_message(f"Starting a {difficulty} quiz in {category_name} with {number_of_questions} questions!")
    await next_question(interaction, interaction.user.id)

async def next_question(interaction, user_id):
    user_data = user_sessions[user_id]
    question_data = user_data["questions"][user_data["current_question"]]

    # Randomize answer choices
    answers = question_data["incorrect_answers"]
    correct_answer = question_data["correct_answer"]
    answers.append(correct_answer)
    random.shuffle(answers)

    # Store correct answer for checking
    user_data["current_correct_answer"] = correct_answer
    user_data["answered"] = False

    # Display the question and answers
    question_text = question_data["question"]
    options = "\n".join([f"{idx + 1}. {ans}" for idx, ans in enumerate(answers)])
    question_message = await interaction.followup.send(f"**Question {user_data['current_question'] + 1}:**\n{question_text}\n\n{options}")

    # Start a 30-second timer for the question
    await asyncio.sleep(30)
    if not user_data["answered"]:
        await question_message.reply(f"Time's up! The correct answer was: {correct_answer}")
        user_data["current_question"] += 1
        await end_or_next(interaction.channel, user_id)

async def answer(channel, user_answer, user):
    for user_id, user_data in user_sessions.items():
        if not user_data["answered"]:
            correct_answer = user_data["current_correct_answer"]
            if user_answer.lower() == correct_answer.lower():
                user_data["score"] += 1
                response = "Correct!"
            else:
                response = f"Wrong! The correct answer was: {correct_answer}"

            user_data["answered"] = True
            await channel.send(f"{user.mention} {response}")

            # Cancel the timer for the current question
            if "question_timer_task" in user_data:
                user_data["question_timer_task"].cancel()

            user_data["current_question"] += 1
            await end_or_next(channel, user_id)
            return

async def end_or_next(channel, user_id):
    user_data = user_sessions[user_id]

    # End quiz if no more questions
    if user_data["current_question"] >= len(user_data["questions"]):
        score = user_data["score"]
        await channel.send(f"Quiz complete! Your final score is {score}/{len(user_data['questions'])}.")
        del user_sessions[user_id]
    else:
        await next_question(channel, user_id)

async def next_question(channel, user_id):
    user_data = user_sessions[user_id]
    question_data = user_data["questions"][user_data["current_question"]]

    # Randomize answer choices
    answers = question_data["incorrect_answers"]
    correct_answer = question_data["correct_answer"]
    answers.append(correct_answer)
    random.shuffle(answers)

    # Store correct answer for checking
    user_data["current_correct_answer"] = correct_answer
    user_data["answered"] = False

    # Display the question and answers
    question_text = question_data["question"]
    options = "\n".join([f"{idx + 1}. {ans}" for idx, ans in enumerate(answers)])
    question_message = await channel.send(f"**Question {user_data['current_question'] + 1}:**\n{question_text}\n\n{options}")

    # Start a 30-second timer for the question
    user_data["question_timer_task"] = asyncio.create_task(
        question_timer(channel, user_id, question_message)
    )

async def question_timer(channel, user_id, question_message):
    await asyncio.sleep(30)
    user_data = user_sessions[user_id]
    if not user_data["answered"]:
        await question_message.reply(f"Time's up! The correct answer was: {user_data['current_correct_answer']}")
        user_data["current_question"] += 1
        await end_or_next(channel, user_id)

@quiz.subcommand(name="answer")
async def answer(interaction: nextcord.Interaction, answer: str):
    if interaction.user.id not in user_sessions:
        await interaction.response.send_message("You haven't started a quiz! Use /quiz start.")
        return

    user_data = user_sessions[interaction.user.id]

    # Prevent answering multiple times
    if user_data["answered"]:
        await interaction.response.send_message("You've already answered this question!", ephemeral=True)
        return

    # Mark as answered
    user_data["answered"] = True
    correct_answer = user_data["current_correct_answer"]

    # Check if the answer is correct
    if answer.lower() == correct_answer.lower():
        user_data["score"] += 1
        response = "Correct!"
    else:
        response = f"Wrong! The correct answer was: {correct_answer}"

    await interaction.response.send_message(response)

    # Cancel the timer for the current question
    if "question_timer_task" in user_data:
        user_data["question_timer_task"].cancel()

    # Move to the next question
    user_data["current_question"] += 1
    await end_or_next(interaction.channel, interaction.user.id)

async def end_or_next(channel, user_id):
    user_data = user_sessions[user_id]

    # End quiz if no more questions
    if user_data["current_question"] >= len(user_data["questions"]):
        score = user_data["score"]
        total_questions = len(user_data["questions"])

        # Create an embed for the final score
        embed = nextcord.Embed(
            title="🎉 Quiz Complete! 🎉",
            description="Thank you for participating in the trivia quiz!",
            color=nextcord.Color.green()
        )
        embed.add_field(name="Final Score", value=f"{score} / {total_questions}", inline=False)
        embed.add_field(
            name="Accuracy",
            value=f"{(score / total_questions) * 100:.2f}%",
            inline=False
        )
        embed.set_footer(text="Play again anytime with /quiz start!")
        embed.set_thumbnail(url="https://example.com/path-to-congratulations-image.png")  # Optional image URL

        await channel.send(embed=embed)
        del user_sessions[user_id]
    else:
        await next_question(channel, user_id)

async def next_question(channel, user_id):
    user_data = user_sessions[user_id]
    question_data = user_data["questions"][user_data["current_question"]]

    # Randomize answer choices
    answers = question_data["incorrect_answers"]
    correct_answer = question_data["correct_answer"]
    answers.append(correct_answer)
    random.shuffle(answers)

    # Store correct answer for checking
    user_data["current_correct_answer"] = correct_answer
    user_data["answered"] = False

    # Display the question and answers
    question_text = question_data["question"]
    options = "\n".join([f"{idx + 1}. {ans}" for idx, ans in enumerate(answers)])
    question_message = await channel.send(f"**Question {user_data['current_question'] + 1}:**\n{question_text}\n\n{options}")

    # Start a 30-second timer for the question
    user_data["question_timer_task"] = asyncio.create_task(
        question_timer(channel, user_id, question_message)
    )

async def question_timer(channel, user_id, question_message):
    await asyncio.sleep(30)
    user_data = user_sessions[user_id]
    if not user_data["answered"]:
        await question_message.reply(f"Time's up! The correct answer was: {user_data['current_correct_answer']}")
        user_data["current_question"] += 1
        await end_or_next(channel, user_id)

@quiz.subcommand(name="score")
async def score(interaction: nextcord.Interaction):
    if interaction.user.id not in user_sessions:
        await interaction.response.send_message("You haven't started a quiz! Use /quiz start.")
        return

    user_data = user_sessions[interaction.user.id]
    score_text = f"Your current score: {user_data['score']} correct answers out of {user_data['current_question']}"
    await interaction.response.send_message(score_text)

# Run the bot
bot.run(TOKEN)
