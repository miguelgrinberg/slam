#!/usr/bin/env python

def fizzbuzz(number):
    answer = []
    if number % 3 == 0:
        answer.append('fizz')
    if number % 5 == 0:
        answer.append('buzz')
    if not answer:
        answer.append(str(number))
    return ' '.join(answer)


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print('Usage: fizzbuzz <number>')
        sys.exit(1)
    print(fizzbuzz(int(sys.argv[1])))
