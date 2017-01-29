def fizzbuzz(number):
    answer = []
    if number % 3 == 0:
        answer.append('fizz')
    if number % 5 == 0:
        answer.append('buzz')
    if not answer:
        answer.append(str(number))
    return ' '.join(answer)
