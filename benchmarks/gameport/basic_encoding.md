# C64 Basic Encoding

The encoding of BASIC programs is relatively straightforward, little more than a 
PETSCII (Commodore’s version of ASCII) rendition of the program with tokens for the commands. 

Before we go into that be aware that PRG files are prefixed with a load address (16-bit little-endian). 
If the command ‘LOAD “file”,8,1’ is used the file is loaded at this address; 
if the ‘LOAD “file”,8’ variant is used it is loaded at $0801 (the “,8” in both these 
examples assumes loading from disc); the load address itself is not loaded with either 
variant. 

On the C64 basic programs start at the hexadecimal address $0801 and can continue 
on to $9fff.

From $0801 onwards the lines follow in line-number order. 
Each line consists of a header, followed by a series of PETSCII characters and tokens, 
and is terminated by a zero. 

Immediately after the terminating zero the next line begins. 
The header of each line consists of two 16-bit (little-endian) unsigned integers. The first 
of these is the line-link; this is a pointer to the start of the next line, a 
line-link with a high byte of $00 marking the end of the program.
 
Normally both bytes of the terminating line-link are zero, only checking 
the high byte is probably an optimization, but as we’ll see later you do come 
across machine language programs with BASIC bootstraps taking advantage of 
this to save two bytes.

These line-links form a linked list so every line of the program can be visited and lines looked up.

The second 16-bit number is the line number. You’d think this would mean 
that line numbers can be in the range 0-65535, but for some reason only 0- 63999 can be used. 

The structure of the rest of a line is a series of PETSCII characters and 
tokens. If the byte has the MSB set it is interpreted as a token and if it’s clear 
it’s a character. Characters inside exclamation marks '"' are not tokenized.


The tokens are listed below:

Value 	Command
$80 	END
$81 	FOR
$82 	NEXT
$83 	DATA
$84 	INPUT#
$85 	INPUT
$86 	DIM
$87 	READ
$88 	LET
$89 	GOTO
$8a 	RUN
$8b 	IF
$8c 	RESTORE
$8d 	GOSUB
$8e 	RETURN
$8f 	REM
$90 	STOP
$91 	ON
$92 	WAIT
$93 	LOAD
$94 	SAVE
$95 	VERIFY
$96 	DEF
$97 	POKE
$98 	PRINT#
$99 	PRINT
$9a 	CONT
$9b 	LIST
$9c 	CLR
$9d 	CMD
$9e 	SYS
$9f 	OPEN
$a0 	CLOSE
$a1 	GET
$a2 	NEW
$a3 	TAB(
$a4 	TO
$a5 	FN
$a6 	SPC(
$a7 	THEN
$a8 	NOT
$a9 	STEP
$aa 	+
$ab 	-
$ac 	*
$ad 	/
$ae 	↑
$af 	AND
$b0 	OR
$b1 	>
$b2 	=
$b3 	<
$b4 	SGN
$b5 	INT
$b6 	ABS
$b7 	USR
$b8 	FRE
$b9 	POS
$ba 	SQR
$bb 	RND
$bc 	LOG
$bd 	EXP
$be 	COS
$bf 	SIN
$c0 	TAN
$c1 	ATN
$c2 	PEEK
$c3 	LEN
$c4 	STR$
$c5 	VAL
$c6 	ASC
$c7 	CHR$
$c8 	LEFT$
$c9 	RIGHT$
$ca 	MID$
$cb 	GO
$ff 	π

Note how the TAB and SPC command come with an embedded opening bracket, the closing one is encoded as a PETSCII character. 
Other commands which require brackets encode both as PETSCII characters following the tokenised command.
