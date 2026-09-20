// Copyright 2026 The RENKU project
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The per-OS half of ChildProcessLauncherHelper. This is the Linux file with
// everything the zygote and the sandbox host contribute taken out: Haiku has
// neither, so every child is launched directly with base::LaunchProcess and
// reaped the plain POSIX way. The rest comes from
// child_process_launcher_helper_posix.cc, which is already in the build.

#include "content/browser/child_process_launcher_helper.h"

#include "base/command_line.h"
#include "base/path_service.h"
#include "base/posix/global_descriptors.h"
#include "base/process/kill.h"
#include "base/process/launch.h"
#include "content/browser/child_process_launcher.h"
#include "content/browser/child_process_launcher_helper_posix.h"
#include "content/browser/sandboxed_process_launcher_delegate.h"
#include "content/public/browser/child_process_launcher_utils.h"
#include "content/public/common/result_codes.h"

namespace content {
namespace internal {

std::optional<mojo::NamedPlatformChannel>
ChildProcessLauncherHelper::CreateNamedPlatformChannelOnLauncherThread() {
  DCHECK(CurrentlyOnProcessLauncherTaskRunner());
  return std::nullopt;
}

void ChildProcessLauncherHelper::BeforeLaunchOnClientThread() {
  DCHECK(client_task_runner_->RunsTasksInCurrentSequence());
}

std::unique_ptr<FileMappedForLaunch>
ChildProcessLauncherHelper::GetFilesToMap() {
  DCHECK(CurrentlyOnProcessLauncherTaskRunner());
  return CreateDefaultPosixFilesToMap(
      child_process_id(), mojo_channel_->remote_endpoint(),
      file_data_->files_to_preload, GetProcessType(), command_line());
}

bool ChildProcessLauncherHelper::IsUsingLaunchOptions() {
  // Always: with no zygote, every child is launched directly.
  return true;
}

bool ChildProcessLauncherHelper::BeforeLaunchOnLauncherThread(
    PosixFileDescriptorInfo& files_to_register,
    base::LaunchOptions* options) {
  DCHECK(options);
  options->fds_to_remap = files_to_register.GetMappingWithIDAdjustment(
      base::GlobalDescriptors::kBaseDescriptor);
  options->environment = delegate_->GetEnvironment();
  return true;
}

ChildProcessLauncherHelper::Process
ChildProcessLauncherHelper::LaunchProcessOnLauncherThread(
    const base::LaunchOptions* options,
    std::unique_ptr<FileMappedForLaunch> files_to_register,
    bool* is_synchronous_launch,
    int* launch_result) {
  *is_synchronous_launch = true;
  Process process;
  process.process = base::LaunchProcess(*command_line(), *options);
  *launch_result = process.process.IsValid() ? LAUNCH_RESULT_SUCCESS
                                             : LAUNCH_RESULT_FAILURE;
  return process;
}

void ChildProcessLauncherHelper::AfterLaunchOnLauncherThread(
    const ChildProcessLauncherHelper::Process& process,
    const base::LaunchOptions* options) {
  // Reset any FDs still held open.
  file_data_.reset();
}

ChildProcessTerminationInfo ChildProcessLauncherHelper::GetTerminationInfo(
    const ChildProcessLauncherHelper::Process& process,
    bool known_dead) {
  ChildProcessTerminationInfo info;
  info.status = known_dead ? base::GetKnownDeadTerminationStatus(
                                 process.process.Handle(), &info.exit_code)
                           : base::GetTerminationStatus(process.process.Handle(),
                                                        &info.exit_code);
  return info;
}

// static
bool ChildProcessLauncherHelper::TerminateProcess(const base::Process& process,
                                                  int exit_code) {
  return process.Terminate(exit_code, false);
}

// static
void ChildProcessLauncherHelper::ForceNormalProcessTerminationSync(
    ChildProcessLauncherHelper::Process process) {
  DCHECK(CurrentlyOnProcessLauncherTaskRunner());
  process.process.Terminate(RESULT_CODE_NORMAL_EXIT, false);
  // On POSIX the child has to be reaped as well.
  base::EnsureProcessTerminated(std::move(process.process));
}

void ChildProcessLauncherHelper::SetProcessPriorityOnLauncherThread(
    base::Process process,
    base::Process::Priority priority) {
  DCHECK(CurrentlyOnProcessLauncherTaskRunner());
  if (process.CanSetPriority()) {
    process.SetPriority(priority);
  }
}

base::File OpenFileToShare(const base::FilePath& path,
                           base::MemoryMappedFile::Region* region) {
  base::FilePath exe_dir;
  bool result = base::PathService::Get(base::BasePathKey::DIR_EXE, &exe_dir);
  DCHECK(result);
  base::File file(exe_dir.Append(path),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  *region = base::MemoryMappedFile::Region::kWholeFile;
  return file;
}

}  // namespace internal
}  // namespace content
