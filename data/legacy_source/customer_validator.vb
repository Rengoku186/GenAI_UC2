' ====================================================================
' CUSTOMER VALIDATION AND SCORING MODULE
' LEGACY VISUAL BASIC / VB.NET BUSINESS LOGIC
' ====================================================================

Imports System
Imports System.Text.RegularExpressions

Namespace LegacyEnterprise.Validation

    Public Class CustomerValidator
        
        Private Const MIN_AGE As Integer = 18
        Private Const MAX_AGE As Integer = 120
        Private Const MIN_CREDIT_SCORE As Integer = 300
        Private Const MAX_CREDIT_SCORE As Integer = 850
        
        ' Structure for Customer Data Payload
        Public Structure CustomerRecord
            Public CustomerId As String
            Public FullName As String
            Public Age As Integer
            Public CreditScore As Integer
            Public AnnualIncome As Double
            Public TotalDebt As Double
            Public Email As String
            Public IsActive As Boolean
        End Structure

        ' Result container for validation outcome
        Public Structure ValidationResult
            Public IsValid As Boolean
            Public RiskCategory As String
            Public MaxLoanEligibility As Double
            Public DebtToIncomeRatio As Double
            Public ErrorMessages As String()
        End Structure

        ' Main Entry Validation Method
        Public Function ValidateCustomer(ByVal cust As CustomerRecord) As ValidationResult
            Dim result As ValidationResult
            Dim errors As New System.Collections.Generic.List(Of String)()
            
            ' Validate Age
            If cust.Age < MIN_AGE Or cust.Age > MAX_AGE Then
                errors.Add("Customer age must be between 18 and 120.")
            End If

            ' Validate Credit Score Range
            If cust.CreditScore < MIN_CREDIT_SCORE Or cust.CreditScore > MAX_CREDIT_SCORE Then
                errors.Add("Credit score is out of standard range (300-850).")
            End If

            ' Validate Email format
            If String.IsNullOrEmpty(cust.Email) Or Not Regex.IsMatch(cust.Email, "^[^@\s]+@[^@\s]+\.[^@\s]+$") Then
                errors.Add("Invalid customer email address format.")
            End If

            ' Compute Debt to Income Ratio
            Dim dti As Double = 0.0
            If cust.AnnualIncome > 0 Then
                dti = (cust.TotalDebt / cust.AnnualIncome) * 100.0
            Else
                dti = 999.99
                errors.Add("Annual income must be strictly greater than zero.")
            End If
            result.DebtToIncomeRatio = Math.Round(dti, 2)

            ' Check if active
            If Not cust.IsActive Then
                errors.Add("Inactive customer accounts cannot be processed for credit.")
            End If

            ' Evaluate Risk Category and Loan Limit
            If errors.Count = 0 Then
                result.IsValid = True
                result.RiskCategory = DetermineRiskCategory(cust.CreditScore, dti)
                result.MaxLoanEligibility = CalculateLoanLimit(cust.AnnualIncome, result.RiskCategory)
            Else
                result.IsValid = False
                result.RiskCategory = "REJECTED"
                result.MaxLoanEligibility = 0.0
            End If

            result.ErrorMessages = errors.ToArray()
            Return result
        End Function

        Private Function DetermineRiskCategory(ByVal score As Integer, ByVal dti As Double) As String
            If score >= 750 And dti <= 35.0 Then
                Return "LOW_RISK_PRIME"
            ElseIf score >= 650 And dti <= 45.0 Then
                Return "MEDIUM_RISK_STANDARD"
            ElseIf score >= 580 And dti <= 50.0 Then
                Return "HIGH_RISK_SUBPRIME"
            Else
                Return "INELIGIBLE"
            End If
        End Function

        Private Function CalculateLoanLimit(ByVal income As Double, ByVal riskTier As String) As Double
            Select Case riskTier
                Case "LOW_RISK_PRIME"
                    Return income * 4.5
                Case "MEDIUM_RISK_STANDARD"
                    Return income * 3.0
                Case "HIGH_RISK_SUBPRIME"
                    Return income * 1.5
                Case Else
                    Return 0.0
            End Select
        End Function

    End Class

End Namespace
