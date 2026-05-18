# Gemini Code Assist Instructions

## Environment Constraints

* **Operating System:** Windows
* **Terminal:** PowerShell / Windows Terminal
* **Constraint:** Do NOT use the `replace` command. It conflicts with the Windows OS `replace.exe` utility.

## File Modification Standards

When generating scripts or executing file updates, always use the PowerShell `Set-Content` cmdlet instead of `replace`.

**Preferred Pattern:**

```powershell
Set-Content -Path "<path>" -Value @"
<content>
"@
```

**Avoid Pattern:**

```powershell
replace -Path "<path>" -Value @"
<content>
"@
```

## Note to Gemini from user

Do not run pytest as the test suite is currently broken.
