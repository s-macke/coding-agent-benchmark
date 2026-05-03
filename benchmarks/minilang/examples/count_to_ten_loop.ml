1
loop:
dup print
dup 10 = &done if
1 +
&loop goto
done:
