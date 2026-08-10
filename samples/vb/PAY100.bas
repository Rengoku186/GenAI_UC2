Attribute VB_Name = "PAY100"

Sub MainProcess()
    Call ValidatePayroll
    Call CalculateTax
End Sub

Sub ValidatePayroll()
    If EmployeeCount <= 0 Then
        Call RaiseError
    End If
End Sub

Sub CalculateTax()
    GrossPay = NetPay * 1.2
End Sub

Sub RaiseError()
    MsgBox "Invalid payroll count"
End Sub
