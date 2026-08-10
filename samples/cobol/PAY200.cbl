       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAY200.
       PROCEDURE DIVISION.
       MAIN.
           PERFORM CALC-B
           STOP RUN.

       CALC-B.
           DISPLAY "IN B"
           PERFORM CALC-C.

       CALC-C.
           DISPLAY "IN C"
           PERFORM CALC-B.
