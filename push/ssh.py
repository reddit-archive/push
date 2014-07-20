import select
import getpass
import paramiko


# hack to add paramiko support for AES encrypted private keys
if "AES-128-CBC" not in paramiko.PKey._CIPHER_TABLE:
    from Crypto.Cipher import AES
    paramiko.PKey._CIPHER_TABLE["AES-128-CBC"] = dict(cipher=AES, keysize=16, blocksize=16, mode=AES.MODE_CBC)


class SshError(Exception):
    def __init__(self, code):
        self.code = code

    def __str__(self):
        return "remote command exited with code %d" % self.code


class SshConnection(object):
    def __init__(self, config, log, host):
        self.config = config
        self.log = log
        self.host = host

        self.client = paramiko.SSHClient()
        if not config.ssh.strict_host_key_checking:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(host,
                            username=config.ssh.user,
                            timeout=config.ssh.timeout,
                            pkey=config.ssh.pkey)

    def execute_command(self, command, display_output=False):
        transport = self.client.get_transport()
        channel = transport.open_session()
        channel.settimeout(self.config.ssh.timeout)
        channel.set_combine_stderr(True)
        channel.exec_command(command)
        channel.shutdown_write()

        output = []
        while True:
            readable = select.select([channel], [], [])[0]

            if not readable:
                continue

            received = channel.recv(1024)
            if not received:
                break

            received = unicode(received, "utf-8")

            output.append(received)

            if display_output:
                self.log.write(received, newline=False)

        status_code = channel.recv_exit_status()
        if status_code != 0:
            raise SshError(status_code)

        return "".join(output)

    def close(self):
        self.client.close()


class SshDeployer(object):
    """Executes deploy commands on remote systems using SSH. If multiple
    commands are run on the same host in succession, the same connection is
    reused for each."""

    def __init__(self, config, args, log):
        self.config = config
        self.args = args
        self.log = log
        self.current_connection = None

        config.ssh.pkey = None
        if not config.ssh.key_filename:
            return

        key_classes = (paramiko.RSAKey, paramiko.DSSKey)
        for key_class in key_classes:
            try:
                config.ssh.pkey = key_class.from_private_key_file(
                                                config.ssh.key_filename)
            except paramiko.PasswordRequiredException:
                need_password = True
                break
            except paramiko.SSHException:
                continue
            else:
                need_password = False
                break
        else:
            raise SshError("invalid key file %s" % config.ssh.key_filename)

        tries_remaining = 3
        while need_password and tries_remaining:
            password = getpass.getpass("password for %s: " %
                                       config.ssh.key_filename)

            try:
                config.ssh.pkey = key_class.from_private_key_file(
                                                config.ssh.key_filename,
                                                password=password)
                need_password = False
            except paramiko.SSHException:
                tries_remaining -= 1

        if need_password and not tries_remaining:
            raise SshError("invalid password.")

    def shutdown(self):
        if self.current_connection:
            self.current_connection.close()
            self.current_connection = None

    def _get_connection(self, host):
        if self.current_connection and self.current_connection.host != host:
            self.current_connection.close()
            self.current_connection = None
        if not self.current_connection:
            self.current_connection = SshConnection(self.config, self.log, host)
        return self.current_connection

    def _run_command(self, host, binary, *args, **kwargs):
        command = " ".join(("/usr/bin/sudo", binary) + args)
        self.log.debug(command)

        if not self.args.testing:
            conn = self._get_connection(host)
            display_output = kwargs.get("display_output", True)
            return conn.execute_command(command, display_output=display_output)
        else:
            return "TESTING"

    def run_build_command(self, *args, **kwargs):
        return self._run_command(self.config.deploy.build_host,
                                 self.config.deploy.build_binary,
                                 *args, **kwargs)

    def run_deploy_command(self, host, *args, **kwargs):
        return self._run_command(host,
                                 self.config.deploy.deploy_binary,
                                 *args, **kwargs)
